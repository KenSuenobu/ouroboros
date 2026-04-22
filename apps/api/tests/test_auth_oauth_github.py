"""GitHub OAuth login flow with mocked HTTP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.config import settings
from ouroboros_api.db.models import Base, OAuthAccount, User, Workspace, WorkspaceMembership
from ouroboros_api.main import create_app
from ouroboros_api.secrets import secrets as secrets_backend
from ouroboros_api.services import oauth_github


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(self, *, token: str, profile: dict, emails: list | None = None):
        self.token = token
        self.profile = profile
        self.emails = emails or []
        self.posted: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, data=None, headers=None, timeout=None):
        self.posted.append((url, data or {}))
        return _FakeResponse(200, {"access_token": self.token, "token_type": "bearer"})

    async def get(self, url, headers=None, timeout=None):
        self.gets.append(url)
        if "/user/emails" in url:
            return _FakeResponse(200, self.emails)
        return _FakeResponse(200, self.profile)


@pytest_asyncio.fixture
async def stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "oauth.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with factory() as session:
        session.add(Workspace(slug=settings.default_workspace_slug, name="Default Workspace"))
        await session.commit()

    monkeypatch.setattr(settings, "login_github_oauth_client_id", "test_client_id")
    monkeypatch.setattr(settings, "web_base_url", "http://test")
    secrets_backend.set(settings.login_github_oauth_client_secret_ref, "test_client_secret")

    app = create_app()

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan  # type: ignore[method-assign]

    async def override_db_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps.db_session] = override_db_session

    yield app, factory

    app.dependency_overrides.clear()
    await engine.dispose()
    secrets_backend.delete(settings.login_github_oauth_client_secret_ref)


@pytest.mark.asyncio
async def test_oauth_disabled_when_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "login_github_oauth_client_id", "")
    db_path = tmp_path / "no-oauth.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan  # type: ignore[method-assign]

    async def override_db_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps.db_session] = override_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status = await client.get("/api/auth/status")
        assert status.json()["github_oauth_enabled"] is False

        start = await client.get("/api/auth/oauth/github/start")
        assert start.status_code == 404

    await engine.dispose()


@pytest.mark.asyncio
async def test_oauth_start_redirects_to_github(stack) -> None:
    app, _ = stack
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        res = await client.get("/api/auth/oauth/github/start")
    assert res.status_code == 302
    location = res.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize")
    assert "client_id=test_client_id" in location
    assert "state=" in location
    state_cookie = res.cookies.get(oauth_github.OAUTH_STATE_COOKIE)
    assert state_cookie


@pytest.mark.asyncio
async def test_oauth_callback_creates_user_and_logs_in(
    stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, factory = stack

    profile = {
        "id": 12345,
        "login": "octocat",
        "name": "The Octocat",
        "email": "octocat@example.com",
    }
    fake = _FakeClient(token="gho_xxxx", profile=profile)
    monkeypatch.setattr(oauth_github.httpx, "AsyncClient", lambda **_: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        start = await client.get("/api/auth/oauth/github/start")
        state = start.cookies.get(oauth_github.OAUTH_STATE_COOKIE)
        assert state

        callback = await client.get(
            "/api/auth/oauth/github/callback",
            params={"code": "auth-code", "state": state},
        )

    assert callback.status_code == 302, callback.text
    assert callback.cookies.get(settings.auth_session_cookie_name)

    async with factory() as session:
        users = (await session.execute(select(User))).scalars().all()
        assert len(users) == 1 and users[0].email == "octocat@example.com"
        accounts = (await session.execute(select(OAuthAccount))).scalars().all()
        assert len(accounts) == 1
        assert accounts[0].provider == "github"
        assert accounts[0].provider_account_id == "12345"
        memberships = (await session.execute(select(WorkspaceMembership))).scalars().all()
        assert len(memberships) == 1
        assert memberships[0].role == "member"


@pytest.mark.asyncio
async def test_oauth_callback_links_existing_user_by_email(
    stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, factory = stack

    async with factory() as session:
        ws = (await session.execute(select(Workspace))).scalar_one()
        existing = User(
            email="octocat@example.com",
            display_name="Octocat",
            password_hash=None,
            is_active=True,
        )
        session.add(existing)
        await session.flush()
        session.add(
            WorkspaceMembership(user_id=existing.id, workspace_id=ws.id, role="admin")
        )
        await session.commit()
        existing_id = existing.id

    fake = _FakeClient(
        token="gho_xxxx",
        profile={"id": 99, "login": "octocat", "name": "Octocat", "email": "octocat@example.com"},
    )
    monkeypatch.setattr(oauth_github.httpx, "AsyncClient", lambda **_: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        start = await client.get("/api/auth/oauth/github/start")
        state = start.cookies.get(oauth_github.OAUTH_STATE_COOKIE)

        callback = await client.get(
            "/api/auth/oauth/github/callback",
            params={"code": "abc", "state": state},
        )
    assert callback.status_code == 302

    async with factory() as session:
        accounts = (await session.execute(select(OAuthAccount))).scalars().all()
        assert len(accounts) == 1
        assert accounts[0].user_id == existing_id


@pytest.mark.asyncio
async def test_oauth_callback_rejects_bad_state(stack) -> None:
    app, _ = stack
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        await client.get("/api/auth/oauth/github/start")
        # Send a different state value
        res = await client.get(
            "/api/auth/oauth/github/callback",
            params={"code": "abc", "state": "wrong-state"},
        )
    assert res.status_code == 400
