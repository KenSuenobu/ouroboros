"""Password hashing + session management.

Sessions are opaque random tokens delivered to the client via cookie.
We store only a SHA-256 of each token in the `sessions` table so a stolen
DB does not let an attacker forge cookies.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Session, User

_hasher = PasswordHasher()
_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed or not password:
        return False
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except Exception:
        return False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_session(
    db: AsyncSession,
    user: User,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    ttl_days: int | None = None,
) -> tuple[str, Session]:
    """Create a session row and return (raw_token, session). Caller commits."""
    raw = secrets.token_urlsafe(_TOKEN_BYTES)
    days = ttl_days if ttl_days is not None else settings.auth_session_ttl_days
    session = Session(
        id=_hash_token(raw),
        user_id=user.id,
        expires_at=_now() + timedelta(days=days),
        last_seen_at=_now(),
        ip=ip,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(session)
    return raw, session


async def resolve_session(db: AsyncSession, raw_token: str) -> tuple[Session, User] | None:
    """Validate a raw token. Returns (session, user) or None when expired/missing.

    Touches `last_seen_at` and lazily slides `expires_at` forward.
    Caller is responsible for committing.
    """
    if not raw_token:
        return None
    sid = _hash_token(raw_token)
    row = (
        await db.execute(
            select(Session, User).join(User, User.id == Session.user_id).where(Session.id == sid)
        )
    ).first()
    if not row:
        return None
    session, user = row
    if not user.is_active:
        return None
    now = _now()
    if session.expires_at <= now:
        await db.delete(session)
        return None
    session.last_seen_at = now
    # Sliding expiration: extend if we are within the bottom half of the TTL.
    half = timedelta(days=settings.auth_session_ttl_days // 2 or 1)
    if session.expires_at - now < half:
        session.expires_at = now + timedelta(days=settings.auth_session_ttl_days)
    return session, user


async def revoke_session(db: AsyncSession, raw_token: str) -> None:
    if not raw_token:
        return
    await db.execute(delete(Session).where(Session.id == _hash_token(raw_token)))


async def revoke_all_for_user(db: AsyncSession, user_id: str) -> None:
    await db.execute(delete(Session).where(Session.user_id == user_id))


async def purge_expired(db: AsyncSession) -> int:
    res = await db.execute(delete(Session).where(Session.expires_at <= _now()))
    return res.rowcount or 0
