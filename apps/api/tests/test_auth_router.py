"""End-to-end tests for /api/auth/* (setup, login, me, logout, password, register)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.config import settings
from ouroboros_api.db.models import Base, User, Workspace, WorkspaceMembership
from ouroboros_api.main import create_app
from ouroboros_api.services import auth as auth_svc


@pytest_asyncio.fixture
async def app_factory(tmp_path: Path) -> AsyncIterator[
    tuple[
        callable,
        async_sessionmaker[AsyncSession],
    ]
]:
    db_path = tmp_path / "auth-router-test.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    def make_app(seed_default_workspace: bool = True):
        app = create_app()

        @asynccontextmanager
        async def noop_lifespan(_app):
            yield

        app.router.lifespan_context = noop_lifespan  # type: ignore[method-assign]

        async def override_db_session() -> AsyncIterator[AsyncSession]:
            async with factory() as session:
                yield session

        app.dependency_overrides[deps.db_session] = override_db_session
        return app

    if True:
        async with factory() as session:
            session.add(Workspace(slug=settings.default_workspace_slug, name="Default Workspace"))
            await session.commit()

    yield make_app, factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_status_reports_needs_setup(app_factory) -> None:
    make_app, _ = app_factory
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/auth/status")
    assert res.status_code == 200
    body = res.json()
    assert body["needs_setup"] is True
    assert body["open_registration"] is False


@pytest.mark.asyncio
async def test_setup_creates_first_admin_and_logs_in(
    app_factory,
) -> None:
    make_app, factory = app_factory
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/auth/setup",
            json={
                "email": "Owner@Example.com",
                "password": "supersecret123",
                "display_name": "Owner",
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "owner@example.com"
    assert body["display_name"] == "Owner"
    assert body["has_password"] is True
    assert len(body["memberships"]) == 1
    assert body["memberships"][0]["role"] == "admin"
    cookie = res.cookies.get(settings.auth_session_cookie_name)
    assert cookie

    async with factory() as session:
        users = (await session.execute(__import__("sqlalchemy").select(User))).scalars().all()
        assert len(users) == 1
        memberships = (
            await session.execute(__import__("sqlalchemy").select(WorkspaceMembership))
        ).scalars().all()
        assert len(memberships) == 1 and memberships[0].role == "admin"


@pytest.mark.asyncio
async def test_setup_blocked_when_users_exist(app_factory) -> None:
    make_app, factory = app_factory
    app = make_app()
    async with factory() as session:
        u = User(
            email="existing@example.com",
            display_name="x",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        session.add(u)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/auth/setup",
            json={"email": "another@example.com", "password": "password1"},
        )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_setup_validates_input(app_factory) -> None:
    make_app, _ = app_factory
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_email = await client.post(
            "/api/auth/setup",
            json={"email": "not-an-email", "password": "password1"},
        )
        weak_pw = await client.post(
            "/api/auth/setup",
            json={"email": "ok@example.com", "password": "short"},
        )
    assert bad_email.status_code == 400
    assert weak_pw.status_code == 400


@pytest.mark.asyncio
async def test_login_logout_and_me(app_factory) -> None:
    make_app, factory = app_factory
    app = make_app()
    async with factory() as session:
        ws = (
            await session.execute(
                __import__("sqlalchemy").select(Workspace).where(Workspace.slug == "default")
            )
        ).scalar_one()
        u = User(
            email="alice@example.com",
            display_name="Alice",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        session.add(u)
        await session.flush()
        session.add(WorkspaceMembership(user_id=u.id, workspace_id=ws.id, role="member"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad = await client.post(
            "/api/auth/login", json={"email": "alice@example.com", "password": "wrong"}
        )
        assert bad.status_code == 401

        ok = await client.post(
            "/api/auth/login", json={"email": "alice@example.com", "password": "password1"}
        )
        assert ok.status_code == 200, ok.text
        assert ok.cookies.get(settings.auth_session_cookie_name)

        me = await client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == "alice@example.com"
        assert me.json()["memberships"][0]["role"] == "member"

        out = await client.post("/api/auth/logout")
        assert out.status_code == 204

        me2 = await client.get("/api/auth/me")
        assert me2.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_authentication(app_factory) -> None:
    make_app, _ = app_factory
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_existing_sessions(app_factory) -> None:
    make_app, factory = app_factory
    app = make_app()
    async with factory() as session:
        ws = (
            await session.execute(
                __import__("sqlalchemy").select(Workspace).where(Workspace.slug == "default")
            )
        ).scalar_one()
        u = User(
            email="bob@example.com",
            display_name="Bob",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        session.add(u)
        await session.flush()
        session.add(WorkspaceMembership(user_id=u.id, workspace_id=ws.id, role="member"))
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/auth/login", json={"email": "bob@example.com", "password": "password1"}
        )
        # Session is set as a cookie. Changing password should revoke it.
        ch = await client.post(
            "/api/auth/password",
            json={"current_password": "password1", "new_password": "newpassword2"},
        )
        assert ch.status_code == 200

        me = await client.get("/api/auth/me")
        assert me.status_code == 401

        ok = await client.post(
            "/api/auth/login", json={"email": "bob@example.com", "password": "newpassword2"}
        )
        assert ok.status_code == 200


@pytest.mark.asyncio
async def test_register_off_by_default(app_factory) -> None:
    make_app, _ = app_factory
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "password1"},
        )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_register_when_open(app_factory, monkeypatch) -> None:
    make_app, _ = app_factory
    monkeypatch.setattr(settings, "auth_open_registration", True)
    app = make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "password1", "display_name": "New"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["email"] == "new@example.com"

        # Now should be able to log in
        login = await client.post(
            "/api/auth/login",
            json={"email": "new@example.com", "password": "password1"},
        )
        assert login.status_code == 200
        # Member by default
        assert login.json()["memberships"][0]["role"] == "member"


@pytest.mark.asyncio
async def test_bearer_token_works(app_factory) -> None:
    """Verify CLI-style bearer token authentication."""
    make_app, factory = app_factory
    app = make_app()
    async with factory() as session:
        ws = (
            await session.execute(
                __import__("sqlalchemy").select(Workspace).where(Workspace.slug == "default")
            )
        ).scalar_one()
        u = User(
            email="cli@example.com",
            display_name="CLI",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        session.add(u)
        await session.flush()
        session.add(WorkspaceMembership(user_id=u.id, workspace_id=ws.id, role="admin"))
        raw, _ = await auth_svc.create_session(session, u)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert res.status_code == 200
    assert res.json()["email"] == "cli@example.com"
