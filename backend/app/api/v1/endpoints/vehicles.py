from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.db.models.battery import BatteryReport
from app.db.models.claim import Claim
from app.db.models.enums import UserRole
from app.db.models.parts import PartEvent, VehiclePart
from app.db.models.user import User
from app.db.models.vehicle import Vehicle
from app.ml.telemetry_sim import PROFILES
from app.services import telemetry_service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("/{vin}/simulate-telemetry")
async def simulate_telemetry(
    vin: str,
    profile: str = Query("normal"),
    days: int = Query(180, ge=14, le=730),
    current: User = Depends(require_role(UserRole.admin, UserRole.mechanic)),
    db: AsyncSession = Depends(get_db),
):
    if profile not in PROFILES:
        profile = "normal"
    n = await telemetry_service.simulate(db, current.tenant_id, vin, profile=profile, days=days)
    await db.commit()
    return {"vin": vin.upper(), "profile": profile, "snapshots": n}


@router.get("/{vin}/telemetry")
async def get_telemetry(
    vin: str,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assessment = await telemetry_service.assess(db, current.tenant_id, vin)
    veh = await db.scalar(
        select(Vehicle).where(
            Vehicle.tenant_id == current.tenant_id, Vehicle.vin == vin.strip().upper()
        )
    )
    return {
        "vin": vin.upper(),
        "profile": veh.telemetry_profile if veh else None,
        **assessment,
    }


@router.get("")
async def list_vehicles(
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Known vehicles for the tenant (from the master + any VIN seen on a claim)."""
    vehicles = list(
        await db.scalars(
            select(Vehicle).where(Vehicle.tenant_id == current.tenant_id)
            .order_by(Vehicle.vin)
        )
    )
    known = {v.vin for v in vehicles}
    out = [
        {"vin": v.vin, "make": v.make, "model": v.model,
         "profile": v.telemetry_profile}
        for v in vehicles
    ]
    # Include VINs that appear on claims but have no master row yet.
    claim_vins = await db.scalars(
        select(Claim.vin).where(
            Claim.tenant_id == current.tenant_id, Claim.vin.is_not(None)
        ).distinct()
    )
    for vin in claim_vins:
        if vin and vin not in known:
            out.append({"vin": vin, "make": None, "model": None, "profile": None})
            known.add(vin)
    return out


@router.get("/{vin}/passport")
async def vehicle_passport(
    vin: str,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate everything WarrantyLens knows about a vehicle (digital passport)."""
    vin = vin.strip().upper()
    tid = current.tenant_id

    veh = await db.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tid, Vehicle.vin == vin)
    )
    parts = list(
        await db.scalars(
            select(VehiclePart).where(VehiclePart.tenant_id == tid, VehiclePart.vin == vin)
            .order_by(VehiclePart.component_code)
        )
    )
    claims = list(
        await db.scalars(
            select(Claim).where(Claim.tenant_id == tid, Claim.vin == vin)
            .order_by(Claim.created_at.desc())
        )
    )
    events = list(
        await db.scalars(
            select(PartEvent).where(PartEvent.tenant_id == tid, PartEvent.vin == vin)
            .order_by(PartEvent.created_at.desc()).limit(50)
        )
    )
    battery = list(
        await db.scalars(
            select(BatteryReport).where(BatteryReport.tenant_id == tid, BatteryReport.vin == vin)
            .order_by(BatteryReport.created_at.desc()).limit(5)
        )
    )
    telemetry = await telemetry_service.assess(db, tid, vin)

    return {
        "vin": vin,
        "vehicle": {
            "make": veh.make if veh else None,
            "model": veh.model if veh else None,
            "profile": veh.telemetry_profile if veh else None,
            "manufactured_at": (
                veh.manufactured_at.isoformat() if veh and veh.manufactured_at else None
            ),
        } if veh else None,
        "parts": [
            {"serial": p.serial, "component_code": p.component_code, "is_active": p.is_active}
            for p in parts
        ],
        "claims": [
            {"id": str(c.id), "claim_number": c.claim_number, "status": c.status.value,
             "risk_score": float(c.risk_score) if c.risk_score is not None else None,
             "created_at": c.created_at.isoformat()}
            for c in claims
        ],
        "part_events": [
            {"serial": e.serial, "event_type": e.event_type.value,
             "created_at": e.created_at.isoformat()}
            for e in events
        ],
        "battery_reports": [
            {"id": str(b.id), "soh_percent": b.soh_percent, "rul_cycles": b.rul_cycles,
             "warranty_leaning": b.warranty_leaning, "created_at": b.created_at.isoformat()}
            for b in battery
        ],
        "telemetry": telemetry,
    }
