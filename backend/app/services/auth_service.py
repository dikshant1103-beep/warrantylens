from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.services import user_service


async def authenticate(
    session: AsyncSession, *, email: str, password: str, tenant_slug: str | None
) -> User:
    tenant_id = None
    if tenant_slug:
        tenant = await session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            raise AuthenticationError("Invalid credentials")
        tenant_id = tenant.id

    candidates = await user_service.get_by_email(session, email, tenant_id)
    if not candidates:
        raise AuthenticationError("Invalid credentials")
    if len(candidates) > 1:
        raise AuthenticationError(
            "Email exists in multiple tenants; provide tenant_slug"
        )

    user = candidates[0]
    if not user.is_active or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid credentials")

    user.last_login_at = datetime.now(UTC)
    await session.flush()
    return user


async def issue_refresh_token(
    session: AsyncSession, user: User, *, user_agent: str | None, ip: str | None
) -> str:
    raw = generate_refresh_token()
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        expires_at=refresh_token_expiry(),
        user_agent=user_agent,
        ip=ip,
    )
    session.add(token)
    await session.flush()
    return raw


def new_access_token(user: User) -> str:
    return create_access_token(
        user_id=user.id, tenant_id=user.tenant_id, role=user.role.value
    )


async def rotate_refresh_token(
    session: AsyncSession, raw_token: str, *, user_agent: str | None, ip: str | None
) -> tuple[User, str, str]:
    """Validate a refresh token, revoke it, issue a new pair. Returns (user, access, refresh)."""
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if token is None or not token.is_active:
        raise AuthenticationError("Invalid or expired refresh token")

    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid or expired refresh token")

    # Rotate: revoke old, issue new.
    token.revoked_at = datetime.now(UTC)
    new_raw = await issue_refresh_token(session, user, user_agent=user_agent, ip=ip)
    return user, new_access_token(user), new_raw


async def revoke_refresh_token(session: AsyncSession, raw_token: str) -> None:
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if token and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        await session.flush()
