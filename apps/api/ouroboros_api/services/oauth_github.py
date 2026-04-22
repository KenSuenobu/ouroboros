"""GitHub OAuth (login flow). Distinct from the per-project SCM OAuth.

The GitHub *application* (Client ID + Client Secret) is configured by the
operator. Authorize redirects to GitHub; the callback exchanges the code
for an access token, looks up the GitHub user, then either logs in an
existing OAuthAccount or provisions a new User + OAuthAccount + workspace
membership.
"""

from __future__ import annotations

import secrets as stdlib_secrets
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import OAuthAccount, User, Workspace, WorkspaceMembership
from ..secrets import secrets

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_USER = "https://api.github.com/user"
GITHUB_API_USER_EMAILS = "https://api.github.com/user/emails"

OAUTH_STATE_COOKIE = "ob_oauth_state"
OAUTH_STATE_TTL_SECONDS = 300


def is_enabled() -> bool:
    return bool(settings.login_github_oauth_client_id) and bool(_client_secret())


def _client_secret() -> str | None:
    return secrets.get(settings.login_github_oauth_client_secret_ref)


def authorize_url(*, state: str, redirect_uri: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": settings.login_github_oauth_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "false",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def make_state() -> str:
    return stdlib_secrets.token_urlsafe(24)


async def exchange_code(
    code: str,
    *,
    redirect_uri: str,
    http_client: httpx.AsyncClient | None = None,
) -> str:
    """Exchange an authorization code for a user access token."""
    secret = _client_secret()
    if not secret:
        raise RuntimeError("github oauth client secret is not configured")

    payload = {
        "client_id": settings.login_github_oauth_client_id,
        "client_secret": secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}

    async def _do(client: httpx.AsyncClient) -> str:
        res = await client.post(GITHUB_TOKEN_URL, data=payload, headers=headers, timeout=15.0)
        if res.status_code != 200:
            raise RuntimeError(f"GitHub token exchange failed: HTTP {res.status_code}")
        body = res.json()
        if "error" in body:
            raise RuntimeError(
                f"GitHub token exchange error: {body.get('error_description') or body['error']}"
            )
        token = body.get("access_token")
        if not token:
            raise RuntimeError("GitHub token exchange returned no access_token")
        return token

    if http_client is not None:
        return await _do(http_client)
    async with httpx.AsyncClient() as client:
        return await _do(client)


async def fetch_user_profile(
    access_token: str, *, http_client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Return {provider_account_id, email, display_name}."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ouroboros",
    }

    async def _do(client: httpx.AsyncClient) -> dict[str, Any]:
        u = await client.get(GITHUB_API_USER, headers=headers, timeout=15.0)
        u.raise_for_status()
        user = u.json()
        email = user.get("email")
        if not email:
            e = await client.get(GITHUB_API_USER_EMAILS, headers=headers, timeout=15.0)
            if e.status_code == 200:
                emails = e.json() or []
                primary = next(
                    (
                        x for x in emails
                        if isinstance(x, dict) and x.get("primary") and x.get("verified")
                    ),
                    None,
                )
                email = primary["email"] if primary else (emails[0]["email"] if emails else None)
        if not email:
            raise RuntimeError("GitHub did not return a usable email address")
        return {
            "provider_account_id": str(user["id"]),
            "email": email.lower(),
            "display_name": user.get("name") or user.get("login") or email.split("@")[0],
            "login": user.get("login"),
        }

    if http_client is not None:
        return await _do(http_client)
    async with httpx.AsyncClient() as client:
        return await _do(client)


async def upsert_oauth_user(
    db: AsyncSession,
    *,
    profile: dict[str, Any],
    access_token: str,
) -> User:
    """Find-or-create the OAuthAccount/User, ensure default workspace membership."""
    provider = "github"
    account = (
        await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == profile["provider_account_id"],
            )
        )
    ).scalar_one_or_none()

    if account is not None:
        user = await db.get(User, account.user_id)
        if user is None:
            raise RuntimeError("OAuth account references a missing user")
    else:
        user = (
            await db.execute(select(User).where(User.email == profile["email"]))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=profile["email"],
                display_name=profile["display_name"],
                is_active=True,
            )
            db.add(user)
            await db.flush()
        account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_account_id=profile["provider_account_id"],
        )
        db.add(account)
        await db.flush()

    secret_ref = f"oauth:{provider}:{user.id}"
    secrets.set(secret_ref, access_token)
    account.access_token_secret_ref = secret_ref

    ws = (
        await db.execute(
            select(Workspace).where(Workspace.slug == settings.default_workspace_slug)
        )
    ).scalar_one_or_none()
    if ws is not None:
        membership = (
            await db.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.workspace_id == ws.id,
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            db.add(
                WorkspaceMembership(user_id=user.id, workspace_id=ws.id, role="member")
            )

    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    return user
