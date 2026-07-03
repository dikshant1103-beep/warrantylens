from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.db.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_by_id(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    if user is None:
        raise NotFoundError("User not found")
    return user


async def get_by_email(
    session: AsyncSession, email: str, tenant_id: uuid.UUID | None = None
) -> list[User]:
    stmt = select(User).where(func.lower(User.email) == email.lower())
    if tenant_id is not None:
        stmt = stmt.where(User.tenant_id == tenant_id)
    return list(await session.scalars(stmt))


async def list_users(
    session: AsyncSession, tenant_id: uuid.UUID, *, page: int, size: int
) -> tuple[list[User], int]:
    base = select(User).where(User.tenant_id == tenant_id)
    total = await session.scalar(
        select(func.count()).select_from(base.subquery())
    )
    rows = await session.scalars(
        base.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def create_user(
    session: AsyncSession, tenant_id: uuid.UUID, data: UserCreate
) -> User:
    existing = await get_by_email(session, data.email, tenant_id)
    if existing:
        raise ConflictError("A user with this email already exists in this tenant")
    user = User(
        tenant_id=tenant_id,
        email=data.email.lower(),
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    await session.flush()
    return user


async def update_user(
    session: AsyncSession, user: User, data: UserUpdate
) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    await session.flush()
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.flush()
