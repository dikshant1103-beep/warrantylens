from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, get_current_user, get_db
from app.db.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserRead
from app.services import audit_service, auth_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    user = await auth_service.authenticate(
        db, email=body.email, password=body.password, tenant_slug=body.tenant_slug
    )
    ua = request.headers.get("user-agent")
    ip = client_ip(request)
    refresh = await auth_service.issue_refresh_token(db, user, user_agent=ua, ip=ip)
    access = auth_service.new_access_token(user)
    await audit_service.record(
        db,
        action="user.login",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=user.id,
        tenant_id=user.tenant_id,
        ip=ip,
    )
    await db.commit()
    return TokenResponse(
        access_token=access, refresh_token=refresh, user=UserRead.model_validate(user)
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    ua = request.headers.get("user-agent")
    ip = client_ip(request)
    _user, access, _new_refresh = await auth_service.rotate_refresh_token(
        db, body.refresh_token, user_agent=ua, ip=ip
    )
    await db.commit()
    # NOTE: rotated refresh token is returned via Set-Cookie by the frontend BFF
    # in production; for the API contract we return the new access token here.
    return AccessTokenResponse(access_token=access)


@router.post("/logout", response_model=Message)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> Message:
    await auth_service.revoke_refresh_token(db, body.refresh_token)
    await db.commit()
    return Message(message="Logged out")


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
