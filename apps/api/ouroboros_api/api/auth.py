"""Authentication: setup, login, logout, current user, register."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import OAuthAccount, User, Workspace, WorkspaceMembership
from ..services import auth as auth_svc
from ..services import oauth_github
from .deps import current_user, db_session, optional_current_user
from .schemas import (
    AuthLoginIn,
    AuthSetupIn,
    AuthStatusOut,
    CurrentUserOut,
    PasswordChangeIn,
    UserOut,
    WorkspaceMembershipOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e):
        raise HTTPException(status_code=400, detail="invalid email address")
    return e


def _validate_password(password: str) -> None:
    if not password or len(password) < 8:
        raise HTTPException(
            status_code=400, detail="password must be at least 8 characters long"
        )


def _login_github_oauth_enabled() -> bool:
    return oauth_github.is_enabled()


def _github_callback_url(request: Request) -> str:
    base = settings.web_base_url.rstrip("/") if settings.web_base_url else ""
    if base:
        return f"{base}/api/auth/oauth/github/callback"
    return str(request.url_for("github_oauth_callback"))


async def _users_exist(session: AsyncSession) -> bool:
    count = await session.scalar(select(func.count(User.id)))
    return bool(count and count > 0)


async def _serialize_user(session: AsyncSession, user: User) -> UserOut:
    oauth = (
        await session.execute(
            select(OAuthAccount.provider).where(OAuthAccount.user_id == user.id)
        )
    ).scalars().all()
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        has_password=bool(user.password_hash),
        linked_oauth=list(oauth),
    )


async def _serialize_current_user(session: AsyncSession, user: User) -> CurrentUserOut:
    base = await _serialize_user(session, user)
    rows = (
        await session.execute(
            select(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(WorkspaceMembership.user_id == user.id)
            .order_by(Workspace.created_at)
        )
    ).all()
    memberships = [
        WorkspaceMembershipOut(
            workspace_id=ws.id,
            workspace_slug=ws.slug,
            workspace_name=ws.name,
            role=m.role,
        )
        for m, ws in rows
    ]
    return CurrentUserOut(**base.model_dump(), memberships=memberships)


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=raw_token,
        max_age=settings.auth_session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=False,  # dev default; the proxy should override in prod
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path="/",
    )


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/status", response_model=AuthStatusOut)
async def auth_status(session: AsyncSession = Depends(db_session)) -> AuthStatusOut:
    return AuthStatusOut(
        needs_setup=not await _users_exist(session),
        open_registration=settings.auth_open_registration,
        github_oauth_enabled=_login_github_oauth_enabled(),
    )


@router.get("/me", response_model=CurrentUserOut)
async def get_me(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> CurrentUserOut:
    return await _serialize_current_user(session, user)


@router.post("/setup", response_model=CurrentUserOut)
async def setup_first_admin(
    payload: AuthSetupIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> CurrentUserOut:
    if await _users_exist(session):
        raise HTTPException(status_code=409, detail="setup already completed")

    email = _validate_email(payload.email)
    _validate_password(payload.password)

    ws = (
        await session.execute(
            select(Workspace).where(Workspace.slug == settings.default_workspace_slug)
        )
    ).scalar_one_or_none()
    if not ws:
        ws = Workspace(slug=settings.default_workspace_slug, name="Default Workspace")
        session.add(ws)
        await session.flush()

    user = User(
        email=email,
        display_name=(payload.display_name or "").strip() or email.split("@")[0],
        password_hash=auth_svc.hash_password(payload.password),
        is_active=True,
        last_login_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(user)
    await session.flush()

    session.add(WorkspaceMembership(user_id=user.id, workspace_id=ws.id, role="admin"))

    raw, _ = await auth_svc.create_session(
        session, user, ip=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    await session.commit()
    await session.refresh(user)

    _set_session_cookie(response, raw)
    return await _serialize_current_user(session, user)


@router.post("/login", response_model=CurrentUserOut)
async def login(
    payload: AuthLoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
) -> CurrentUserOut:
    email = (payload.email or "").strip().lower()
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if not user or not user.is_active or not auth_svc.verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="invalid email or password")

    if user.password_hash and auth_svc.needs_rehash(user.password_hash):
        user.password_hash = auth_svc.hash_password(payload.password)

    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    raw, _ = await auth_svc.create_session(
        session, user, ip=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    await session.commit()

    _set_session_cookie(response, raw)
    return await _serialize_current_user(session, user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(db_session),
    _user: User | None = Depends(optional_current_user),
) -> Response:
    token = request.cookies.get(settings.auth_session_cookie_name)
    auth_header = request.headers.get("authorization") or ""
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if token:
        await auth_svc.revoke_session(session, token)
        await session.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/password", response_model=UserOut)
async def change_my_password(
    payload: PasswordChangeIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> UserOut:
    if user.password_hash:
        if not payload.current_password or not auth_svc.verify_password(
            payload.current_password, user.password_hash
        ):
            raise HTTPException(status_code=400, detail="current password is incorrect")
    _validate_password(payload.new_password)
    user.password_hash = auth_svc.hash_password(payload.new_password)
    await auth_svc.revoke_all_for_user(session, user.id)
    await session.commit()
    await session.refresh(user)
    return await _serialize_user(session, user)


@router.post("/register", response_model=UserOut, status_code=201)
async def self_register(
    payload: AuthSetupIn,
    session: AsyncSession = Depends(db_session),
    user: User | None = Depends(optional_current_user),
) -> UserOut:
    """Self-service signup, only allowed when `auth_open_registration` is True.

    Admin-created users go through the admin users router instead.
    """
    if not settings.auth_open_registration:
        raise HTTPException(status_code=403, detail="open registration is disabled")
    if user is not None:
        raise HTTPException(status_code=400, detail="already authenticated")

    email = _validate_email(payload.email)
    _validate_password(payload.password)

    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="email already registered")

    ws = (
        await session.execute(
            select(Workspace).where(Workspace.slug == settings.default_workspace_slug)
        )
    ).scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=409, detail="workspace not initialized")

    new_user = User(
        email=email,
        display_name=(payload.display_name or "").strip() or email.split("@")[0],
        password_hash=auth_svc.hash_password(payload.password),
        is_active=True,
    )
    session.add(new_user)
    await session.flush()
    session.add(
        WorkspaceMembership(user_id=new_user.id, workspace_id=ws.id, role="member")
    )
    await session.commit()
    await session.refresh(new_user)
    return await _serialize_user(session, new_user)


@router.get("/oauth/github/start")
async def github_oauth_start(request: Request) -> RedirectResponse:
    if not _login_github_oauth_enabled():
        raise HTTPException(status_code=404, detail="github oauth is not configured")

    state = oauth_github.make_state()
    redirect_uri = _github_callback_url(request)
    url = oauth_github.authorize_url(state=state, redirect_uri=redirect_uri)
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(
        oauth_github.OAUTH_STATE_COOKIE,
        value=state,
        max_age=oauth_github.OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/api/auth",
    )
    return response


@router.get("/oauth/github/callback", name="github_oauth_callback")
async def github_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"github oauth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")

    expected = request.cookies.get(oauth_github.OAUTH_STATE_COOKIE)
    if not expected or expected != state:
        raise HTTPException(status_code=400, detail="invalid oauth state")

    if not _login_github_oauth_enabled():
        raise HTTPException(status_code=404, detail="github oauth is not configured")

    redirect_uri = _github_callback_url(request)
    try:
        access_token = await oauth_github.exchange_code(code, redirect_uri=redirect_uri)
        profile = await oauth_github.fetch_user_profile(access_token)
        user = await oauth_github.upsert_oauth_user(
            session, profile=profile, access_token=access_token
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    raw, _ = await auth_svc.create_session(
        session, user, ip=_client_ip(request), user_agent=request.headers.get("user-agent")
    )
    await session.commit()

    target = settings.auth_post_login_redirect or "/"
    response = RedirectResponse(url=target, status_code=302)
    _set_session_cookie(response, raw)
    response.delete_cookie(oauth_github.OAUTH_STATE_COOKIE, path="/api/auth")
    return response


# Re-exported for the admin users router.
__all__ = ["router", "_serialize_user", "_validate_email", "_validate_password"]
