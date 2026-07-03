import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.db.models.enums import UserRole
from app.db.models.user import User
from app.schemas.catalog import (
    ComponentCreate,
    ComponentRead,
    ComponentUpdate,
    FraudIndicatorCreate,
    FraudIndicatorRead,
    TemplateCreate,
    TemplateRead,
    TemplateUpdate,
)
from app.services import catalog_service

router = APIRouter()


# --- Components --------------------------------------------------------------
@router.get("/components", response_model=list[ComponentRead])
async def list_components(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await catalog_service.list_components(db, current.tenant_id)


@router.post("/components", response_model=ComponentRead, status_code=status.HTTP_201_CREATED)
async def create_component(
    body: ComponentCreate,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    comp = await catalog_service.create_component(db, current.tenant_id, body)
    await db.commit()
    return comp


@router.patch("/components/{component_id}", response_model=ComponentRead)
async def update_component(
    component_id: uuid.UUID,
    body: ComponentUpdate,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    comp = await catalog_service.update_component(db, current.tenant_id, component_id, body)
    await db.commit()
    return comp


# --- Templates ---------------------------------------------------------------
@router.get("/inspection-templates", response_model=list[TemplateRead])
async def list_templates(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await catalog_service.list_templates(db, current.tenant_id)


@router.post(
    "/inspection-templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED
)
async def create_template(
    body: TemplateCreate,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    tpl = await catalog_service.create_template(db, current.tenant_id, body)
    await db.commit()
    return tpl


@router.patch("/inspection-templates/{template_id}", response_model=TemplateRead)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    tpl = await catalog_service.update_template(db, current.tenant_id, template_id, body)
    await db.commit()
    return tpl


# --- Risk indicators ---------------------------------------------------------
@router.get("/fraud-indicators", response_model=list[FraudIndicatorRead])
async def list_indicators(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await catalog_service.list_indicators(db, current.tenant_id)


@router.post(
    "/fraud-indicators", response_model=FraudIndicatorRead, status_code=status.HTTP_201_CREATED
)
async def create_indicator(
    body: FraudIndicatorCreate,
    current: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    ind = await catalog_service.create_indicator(db, current.tenant_id, body)
    await db.commit()
    return ind
