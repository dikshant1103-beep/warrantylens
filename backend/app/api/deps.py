from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.core.tenancy import set_current_tenant
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer active")

    # Bind tenant context for downstream query scoping.
    set_current_tenant(user.tenant_id)
    return user


def require_role(*roles: UserRole):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(
                f"Requires role: {', '.join(r.value for r in roles)}"
            )
        return user

    return _checker


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None
