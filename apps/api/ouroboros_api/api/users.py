"""Admin user management. Restricted to workspace admins."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import User, Workspace, WorkspaceMembership
from ..services import auth as auth_svc
from .auth import _serialize_user, _validate_email, _validate_password
from .deps import current_user, db_session, require_admin, workspace
from .schemas import AdminUserOut, UserCreateIn, UserUpdateIn

router = APIRouter(prefix="/api/users", tags=["admin"])

_VALID_ROLES = {"admin", "member"}


def _check_role(role: str) -> None:
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=400, detail=f"role must be one of {sorted(_VALID_ROLES)}"
        )


async def _admin_count(session: AsyncSession, workspace_id: str) -> int:
    return int(
        await session.scalar(
            select(func.count(WorkspaceMembership.id)).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.role == "admin",
            )
        )
        or 0
    )


async def _serialize_admin_user(
    session: AsyncSession, user: User, role: str
) -> AdminUserOut:
    base = await _serialize_user(session, user)
    return AdminUserOut(**base.model_dump(), role=role)


@router.get(
    "", response_model=list[AdminUserOut], dependencies=[Depends(require_admin)]
)
async def list_users(
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[AdminUserOut]:
    rows = (
        await session.execute(
            select(User, WorkspaceMembership)
            .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
            .where(WorkspaceMembership.workspace_id == ws.id)
            .order_by(User.created_at)
        )
    ).all()
    return [await _serialize_admin_user(session, u, m.role) for u, m in rows]


@router.post(
    "",
    response_model=AdminUserOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_user(
    payload: UserCreateIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> AdminUserOut:
    email = _validate_email(payload.email)
    _check_role(payload.role)
    if payload.password is not None:
        _validate_password(payload.password)

    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="email already registered")

    user = User(
        email=email,
        display_name=(payload.display_name or "").strip() or email.split("@")[0],
        password_hash=auth_svc.hash_password(payload.password) if payload.password else None,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(
        WorkspaceMembership(user_id=user.id, workspace_id=ws.id, role=payload.role)
    )
    await session.commit()
    await session.refresh(user)
    return await _serialize_admin_user(session, user, payload.role)


@router.patch(
    "/{user_id}",
    response_model=AdminUserOut,
    dependencies=[Depends(require_admin)],
)
async def update_user(
    user_id: str,
    payload: UserUpdateIn,
    ws: Workspace = Depends(workspace),
    actor: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> AdminUserOut:
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    membership = (
        await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == ws.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=404, detail="user is not a member of this workspace"
        )

    if payload.display_name is not None:
        target.display_name = payload.display_name.strip() or target.display_name

    if payload.password is not None:
        _validate_password(payload.password)
        target.password_hash = auth_svc.hash_password(payload.password)
        await auth_svc.revoke_all_for_user(session, target.id)

    if payload.is_active is not None:
        if (
            payload.is_active is False
            and membership.role == "admin"
            and await _admin_count(session, ws.id) <= 1
        ):
            raise HTTPException(
                status_code=400, detail="cannot deactivate the last admin of this workspace"
            )
        target.is_active = payload.is_active
        if not payload.is_active:
            await auth_svc.revoke_all_for_user(session, target.id)

    if payload.role is not None:
        _check_role(payload.role)
        if (
            membership.role == "admin"
            and payload.role != "admin"
            and await _admin_count(session, ws.id) <= 1
        ):
            raise HTTPException(
                status_code=400, detail="cannot demote the last admin of this workspace"
            )
        membership.role = payload.role

    await session.commit()
    await session.refresh(target)
    return await _serialize_admin_user(session, target, membership.role)


@router.delete(
    "/{user_id}", status_code=204, dependencies=[Depends(require_admin)]
)
async def remove_membership(
    user_id: str,
    ws: Workspace = Depends(workspace),
    actor: User = Depends(current_user),
    session: AsyncSession = Depends(db_session),
) -> None:
    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="cannot remove yourself")

    membership = (
        await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == ws.id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=404, detail="user is not a member of this workspace"
        )

    if membership.role == "admin" and await _admin_count(session, ws.id) <= 1:
        raise HTTPException(
            status_code=400, detail="cannot remove the last admin of this workspace"
        )

    await session.delete(membership)

    # Local-mode policy: a user with no remaining memberships is fully removed.
    remaining = await session.scalar(
        select(func.count(WorkspaceMembership.id)).where(
            WorkspaceMembership.user_id == user_id
        )
    )
    if not remaining:
        target = await session.get(User, user_id)
        if target:
            await auth_svc.revoke_all_for_user(session, target.id)
            await session.delete(target)

    await session.commit()


# Re-export helpers so tests can import from one place.
__all__ = ["router"]


# Silence linter for the imported settings constant if unused after compile
_ = settings
