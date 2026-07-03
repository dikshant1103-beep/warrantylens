from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.component import Component, FraudIndicatorDef
from app.db.models.inspection_template import InspectionTemplate
from app.schemas.catalog import (
    ComponentCreate,
    ComponentUpdate,
    FraudIndicatorCreate,
    TemplateCreate,
    TemplateUpdate,
)


# --- Components --------------------------------------------------------------
async def list_components(session: AsyncSession, tenant_id: uuid.UUID) -> list[Component]:
    return list(
        await session.scalars(
            select(Component)
            .where(Component.tenant_id == tenant_id)
            .order_by(Component.code)
        )
    )


async def create_component(
    session: AsyncSession, tenant_id: uuid.UUID, data: ComponentCreate
) -> Component:
    dupe = await session.scalar(
        select(Component).where(
            Component.tenant_id == tenant_id, Component.code == data.code
        )
    )
    if dupe:
        raise ConflictError("Component code already exists")
    comp = Component(tenant_id=tenant_id, **data.model_dump())
    session.add(comp)
    await session.flush()
    return comp


async def update_component(
    session: AsyncSession, tenant_id: uuid.UUID, component_id: uuid.UUID, data: ComponentUpdate
) -> Component:
    comp = await session.scalar(
        select(Component).where(
            Component.id == component_id, Component.tenant_id == tenant_id
        )
    )
    if comp is None:
        raise NotFoundError("Component not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(comp, k, v)
    await session.flush()
    return comp


# --- Templates ---------------------------------------------------------------
async def list_templates(session: AsyncSession, tenant_id: uuid.UUID) -> list[InspectionTemplate]:
    return list(
        await session.scalars(
            select(InspectionTemplate)
            .where(InspectionTemplate.tenant_id == tenant_id)
            .order_by(InspectionTemplate.name)
        )
    )


async def create_template(
    session: AsyncSession, tenant_id: uuid.UUID, data: TemplateCreate
) -> InspectionTemplate:
    tpl = InspectionTemplate(tenant_id=tenant_id, **data.model_dump())
    session.add(tpl)
    await session.flush()
    return tpl


async def update_template(
    session: AsyncSession, tenant_id: uuid.UUID, template_id: uuid.UUID, data: TemplateUpdate
) -> InspectionTemplate:
    tpl = await session.scalar(
        select(InspectionTemplate).where(
            InspectionTemplate.id == template_id,
            InspectionTemplate.tenant_id == tenant_id,
        )
    )
    if tpl is None:
        raise NotFoundError("Template not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(tpl, k, v)
    await session.flush()
    return tpl


# --- Risk indicators ---------------------------------------------------------
async def list_indicators(session: AsyncSession, tenant_id: uuid.UUID) -> list[FraudIndicatorDef]:
    return list(
        await session.scalars(
            select(FraudIndicatorDef)
            .where(FraudIndicatorDef.tenant_id == tenant_id)
            .order_by(FraudIndicatorDef.code)
        )
    )


async def create_indicator(
    session: AsyncSession, tenant_id: uuid.UUID, data: FraudIndicatorCreate
) -> FraudIndicatorDef:
    dupe = await session.scalar(
        select(FraudIndicatorDef).where(
            FraudIndicatorDef.tenant_id == tenant_id,
            FraudIndicatorDef.code == data.code,
        )
    )
    if dupe:
        raise ConflictError("Indicator code already exists")
    ind = FraudIndicatorDef(tenant_id=tenant_id, **data.model_dump())
    session.add(ind)
    await session.flush()
    return ind
