"""Tests for the membership + admin guards across routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ouroboros_api.api import deps
from ouroboros_api.db.models import Base, User, Workspace, WorkspaceMembership
from ouroboros_api.main import create_app
from ouroboros_api.services import auth as auth_svc


@pytest_asyncio.fixture
async def stack(tmp_path: Path) -> AsyncIterator[
    tuple[object, async_sessionmaker[AsyncSession], dict[str, str]]
]:
    db_path = tmp_path / "guards.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tokens: dict[str, str] = {}
    async with factory() as session:
        ws = Workspace(slug="default", name="Default Workspace")
        session.add(ws)
        await session.flush()

        admin = User(
            email="admin@example.com",
            display_name="Admin",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        member = User(
            email="member@example.com",
            display_name="Member",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        outsider = User(
            email="outsider@example.com",
            display_name="Outsider",
            password_hash=auth_svc.hash_password("password1"),
            is_active=True,
        )
        session.add_all([admin, member, outsider])
        await session.flush()

        session.add(WorkspaceMembership(user_id=admin.id, workspace_id=ws.id, role="admin"))
        session.add(WorkspaceMembership(user_id=member.id, workspace_id=ws.id, role="member"))
        # `outsider` is intentionally not added to any workspace.

        for u in (admin, member, outsider):
            raw, _ = await auth_svc.create_session(session, u)
            tokens[u.email] = raw
        await session.commit()

    app = create_app()

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.router.lifespan_context = noop_lifespan  # type: ignore[method-assign]

    async def override_db_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[deps.db_session] = override_db_session

    yield app, factory, tokens

    app.dependency_overrides.clear()
    await engine.dispose()


def _bearer(tokens: dict[str, str], email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens[email]}"}


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(stack) -> None:
    app, _, _ = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ("/api/agents", "/api/flows", "/api/providers", "/api/runs"):
            res = await client.get(path)
            assert res.status_code == 401, f"{path} should require auth"


@pytest.mark.asyncio
async def test_outsider_is_not_a_member(stack) -> None:
    app, _, tokens = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agents", headers=_bearer(tokens, "outsider@example.com"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_member_can_read_but_not_admin_write(stack) -> None:
    app, _, tokens = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.get("/api/flows", headers=_bearer(tokens, "member@example.com"))
        assert ok.status_code == 200

        forbidden = await client.post(
            "/api/flows",
            json={"name": "x", "graph": {"nodes": [], "edges": []}},
            headers=_bearer(tokens, "member@example.com"),
        )
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_admin_write(stack) -> None:
    app, _, tokens = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.post(
            "/api/flows",
            json={"name": "x", "graph": {"nodes": [], "edges": []}},
            headers=_bearer(tokens, "admin@example.com"),
        )
    assert ok.status_code == 201, ok.text


@pytest.mark.asyncio
async def test_users_router_admin_only(stack) -> None:
    app, _, tokens = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        member_blocked = await client.get(
            "/api/users", headers=_bearer(tokens, "member@example.com")
        )
        assert member_blocked.status_code == 403
        admin_ok = await client.get(
            "/api/users", headers=_bearer(tokens, "admin@example.com")
        )
        assert admin_ok.status_code == 200
        listed = admin_ok.json()
        assert len(listed) == 2  # admin + member
        emails = {u["email"] for u in listed}
        assert emails == {"admin@example.com", "member@example.com"}


@pytest.mark.asyncio
async def test_admin_cannot_demote_last_admin(stack) -> None:
    app, factory, tokens = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = (
            await client.get(
                "/api/users", headers=_bearer(tokens, "admin@example.com")
            )
        ).json()
        admin_user = next(u for u in listed if u["email"] == "admin@example.com")
        res = await client.patch(
            f"/api/users/{admin_user['id']}",
            json={"role": "member"},
            headers=_bearer(tokens, "admin@example.com"),
        )
    assert res.status_code == 400
    assert "last admin" in res.json()["detail"]


@pytest.mark.asyncio
async def test_admin_can_promote_and_remove_member(stack) -> None:
    app, _, tokens = stack
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = (
            await client.get(
                "/api/users", headers=_bearer(tokens, "admin@example.com")
            )
        ).json()
        member_user = next(u for u in listed if u["email"] == "member@example.com")

        promoted = await client.patch(
            f"/api/users/{member_user['id']}",
            json={"role": "admin"},
            headers=_bearer(tokens, "admin@example.com"),
        )
        assert promoted.status_code == 200

        # Now there are two admins; we can demote the original admin freely.
        listed_again = (
            await client.get(
                "/api/users", headers=_bearer(tokens, "admin@example.com")
            )
        ).json()
        admin_user = next(u for u in listed_again if u["email"] == "admin@example.com")
        demoted = await client.patch(
            f"/api/users/{admin_user['id']}",
            json={"role": "member"},
            headers=_bearer(tokens, "admin@example.com"),
        )
        assert demoted.status_code == 200

        # The new admin (the previous member) can remove the demoted user.
        removed = await client.delete(
            f"/api/users/{admin_user['id']}",
            headers=_bearer(tokens, "member@example.com"),
        )
    assert removed.status_code == 204
