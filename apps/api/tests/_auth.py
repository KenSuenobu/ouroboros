"""Shared test helpers for the post-auth API.

Most tests build their own SQLite + ASGI app and want to skip auth
plumbing entirely. `install_test_admin` does two things:

1. Inserts a User and an admin WorkspaceMembership row tied to the
   workspace identified by `workspace_slug` so any DB code that joins
   memberships works.
2. Overrides FastAPI dependencies so `current_user`, `workspace`,
   `current_membership`, and `require_admin` all resolve without the
   caller providing a session cookie.

Use it as:

    user = await install_test_admin(app, session_factory)
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ouroboros_api.api import deps
from ouroboros_api.db.models import User, Workspace, WorkspaceMembership


async def install_test_admin(
    app,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str = "tester@example.com",
    workspace_slug: str = "default",
    role: str = "admin",
) -> User:
    """Create the user + membership and wire dep overrides."""
    async with session_factory() as session:
        ws = (
            await session.execute(
                select(Workspace).where(Workspace.slug == workspace_slug)
            )
        ).scalar_one_or_none()
        if ws is None:
            raise RuntimeError(
                f"Workspace {workspace_slug!r} does not exist; seed it before "
                f"calling install_test_admin"
            )

        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            user = User(email=email, display_name=email.split("@")[0], is_active=True)
            session.add(user)
            await session.flush()
        existing_member = (
            await session.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.workspace_id == ws.id,
                )
            )
        ).scalar_one_or_none()
        if existing_member is None:
            session.add(
                WorkspaceMembership(user_id=user.id, workspace_id=ws.id, role=role)
            )
        else:
            existing_member.role = role
        await session.commit()
        await session.refresh(user)
        captured_user_id = user.id
        captured_ws_id = ws.id

    async def _user_override(session: AsyncSession = Depends(deps.db_session)) -> User:
        return (
            await session.execute(select(User).where(User.id == captured_user_id))
        ).scalar_one()

    async def _workspace_override(
        session: AsyncSession = Depends(deps.db_session),
    ) -> Workspace:
        return (
            await session.execute(select(Workspace).where(Workspace.id == captured_ws_id))
        ).scalar_one()

    async def _membership_override(
        session: AsyncSession = Depends(deps.db_session),
    ) -> WorkspaceMembership:
        return (
            await session.execute(
                select(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == captured_user_id,
                    WorkspaceMembership.workspace_id == captured_ws_id,
                )
            )
        ).scalar_one()

    app.dependency_overrides[deps.current_user] = _user_override
    app.dependency_overrides[deps.optional_current_user] = _user_override
    app.dependency_overrides[deps.workspace] = _workspace_override
    app.dependency_overrides[deps.current_membership] = _membership_override
    app.dependency_overrides[deps.require_admin] = _membership_override

    return user
