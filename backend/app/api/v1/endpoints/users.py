import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, get_db, require_role
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.schemas.common import Message
from app.schemas.user import UserCreate, UserList, UserRead, UserUpdate
from app.services import audit_service, user_service

router = APIRouter()


@router.get("", response_model=UserList)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> UserList:
    items, total = await user_service.list_users(
        db, current.tenant_id, page=page, size=size
    )
    return UserList(
        items=[UserRead.model_validate(u) for u in items],
        page=page,
        size=size,
        total=total,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    request: Request,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await user_service.create_user(db, current.tenant_id, body)
    await audit_service.record(
        db,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=current.id,
        tenant_id=current.tenant_id,
        after={"email": user.email, "role": user.role.value},
        ip=client_ip(request),
    )
    await db.commit()
    return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await user_service.get_by_id(db, current.tenant_id, user_id)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    user = await user_service.get_by_id(db, current.tenant_id, user_id)
    before = {"role": user.role.value, "is_active": user.is_active}
    user = await user_service.update_user(db, user, body)
    await audit_service.record(
        db,
        action="user.update",
        entity_type="user",
        entity_id=user.id,
        actor_user_id=current.id,
        tenant_id=current.tenant_id,
        before=before,
        after={"role": user.role.value, "is_active": user.is_active},
        ip=client_ip(request),
    )
    await db.commit()
    return UserRead.model_validate(user)


@router.delete("/{user_id}", response_model=Message)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> Message:
    if user_id == current.id:
        from app.core.exceptions import ConflictError

        raise ConflictError("You cannot delete your own account")
    user = await user_service.get_by_id(db, current.tenant_id, user_id)
    await user_service.delete_user(db, user)
    await audit_service.record(
        db,
        action="user.delete",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=current.id,
        tenant_id=current.tenant_id,
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="User deleted")
