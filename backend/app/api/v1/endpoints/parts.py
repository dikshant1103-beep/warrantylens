import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.db.models.enums import UserRole
from app.db.models.parts import PartEvent, VehiclePart
from app.db.models.user import User
from app.schemas.parts import PartEventRead, PartRegister, VehiclePartRead
from app.services import serial_service

router = APIRouter()


@router.post("/vehicle-parts", response_model=VehiclePartRead, status_code=status.HTTP_201_CREATED)
async def register_part(
    body: PartRegister,
    current: User = Depends(require_role(UserRole.admin, UserRole.mechanic)),
    db: AsyncSession = Depends(get_db),
):
    part = await serial_service.register_part(
        db, current.tenant_id, vin=body.vin, serial=body.serial,
        component_code=body.component_code,
    )
    await db.commit()
    return part


@router.get("/vehicle-parts", response_model=list[VehiclePartRead])
async def list_parts(
    vin: str | None = Query(None),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(VehiclePart).where(VehiclePart.tenant_id == current.tenant_id)
    if vin:
        stmt = stmt.where(VehiclePart.vin == vin.strip().upper())
    rows = await db.scalars(stmt.order_by(VehiclePart.created_at.desc()).limit(200))
    return list(rows)


@router.get("/claims/{claim_id}/part-events", response_model=list[PartEventRead])
async def claim_part_events(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(PartEvent)
        .where(PartEvent.tenant_id == current.tenant_id, PartEvent.claim_id == claim_id)
        .order_by(PartEvent.created_at)
    )
    return list(rows)
