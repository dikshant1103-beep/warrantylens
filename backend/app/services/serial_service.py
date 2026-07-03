"""Serial-number lifecycle + anti-'swap-and-sell' checks.

Given a claim's removed/replacement serials, cross-checks them against the
vehicle-parts registry and the OCR evidence, then:
  - logs immutable PartEvents (who claimed/installed which serial on which VIN),
  - updates the registry (mark removed serial inactive; register replacement),
  - returns evidence-linked risk factors for the explainable risk engine.

These are ADVISORY indicators, never automated accusations.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai import OcrResult
from app.db.models.claim import Claim
from app.db.models.component import Component
from app.db.models.enums import OcrFieldType, PartEventType
from app.db.models.parts import PartEvent, VehiclePart

_SCALE = 10.0


def _norm(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip().upper()
    return s or None


async def _component_code(session: AsyncSession, claim: Claim) -> str | None:
    if not claim.component_id:
        return None
    comp = await session.get(Component, claim.component_id)
    return comp.code if comp else None


async def _ocr_serials(session: AsyncSession, claim_id: uuid.UUID) -> set[str]:
    rows = await session.scalars(
        select(OcrResult).where(
            OcrResult.claim_id == claim_id,
            OcrResult.field_type.in_([OcrFieldType.serial, OcrFieldType.vin]),
        )
    )
    return {_norm(r.normalized_value) for r in rows if r.normalized_value}


async def run_checks(session: AsyncSession, claim: Claim) -> list[dict]:
    """Run serial lifecycle checks for a claim. Returns risk-factor dicts and
    mutates registry + part_events (caller commits)."""
    factors: list[dict] = []
    removed = _norm(claim.removed_serial)
    replacement = _norm(claim.replacement_serial)
    code = await _component_code(session, claim)
    vin = _norm(claim.vin)

    def flag(indicator: str, confidence: float, note: str):
        factors.append({
            "indicator": indicator,
            "weight": 3.0,
            "severity": "high",
            "confidence": round(min(confidence, 1.0), 2),
            "contribution": round(3.0 * min(confidence, 1.0) * _SCALE, 2),
            "evidence_refs": [],
            "source": "serial",
            "note": note,
        })

    # --- Removed part checks ---
    if not removed:
        factors.append({
            "indicator": "removed_serial_missing", "weight": 1.0, "severity": "medium",
            "confidence": 1.0, "contribution": 1.0 * _SCALE, "evidence_refs": [],
            "source": "serial",
            "note": "No serial recorded for the part claimed defective.",
        })
    else:
        part = await session.scalar(
            select(VehiclePart).where(
                VehiclePart.tenant_id == claim.tenant_id, VehiclePart.serial == removed
            )
        )
        if part is None:
            flag("serial_not_registered", 1.0,
                 f"Removed serial {removed} is not registered to any vehicle.")
        elif vin and part.vin != vin:
            flag("serial_not_on_vin", 1.0,
                 f"Removed serial {removed} belongs to VIN {part.vin}, not {vin}.")
        elif not part.is_active:
            flag("serial_reused", 1.0,
                 f"Removed serial {removed} was already claimed/removed earlier.")

        # Photographic proof: the claimed serial should appear in the OCR'd evidence.
        ocr = await _ocr_serials(session, claim.id)
        if ocr and removed not in ocr:
            flag("serial_no_photo_proof", 0.7,
                 f"Removed serial {removed} was not detected in any uploaded photo.")

        # Record removal + retire the registry entry.
        if part is not None and part.is_active and (not vin or part.vin == vin):
            part.is_active = False
            part.removed_claim_id = claim.id
        session.add(PartEvent(
            tenant_id=claim.tenant_id, claim_id=claim.id, vin=vin,
            component_code=code, serial=removed, event_type=PartEventType.claimed_removed,
            note="Claimed defective and removed.",
        ))

    # --- Replacement part checks ---
    if replacement:
        if removed and replacement == removed:
            flag("replacement_equals_removed", 1.0,
                 "Replacement serial equals the removed serial — no real swap.")
        else:
            dup = await session.scalar(
                select(VehiclePart).where(
                    VehiclePart.tenant_id == claim.tenant_id,
                    VehiclePart.serial == replacement,
                    VehiclePart.is_active.is_(True),
                )
            )
            if dup is not None:
                flag("replacement_serial_duplicate", 0.9,
                     f"Replacement serial {replacement} is already active on VIN {dup.vin}.")
            else:
                session.add(VehiclePart(
                    tenant_id=claim.tenant_id, vin=vin or "", component_code=code,
                    serial=replacement, is_active=True,
                ))
                session.add(PartEvent(
                    tenant_id=claim.tenant_id, claim_id=claim.id, vin=vin,
                    component_code=code, serial=replacement, event_type=PartEventType.installed,
                    note="Replacement part installed.",
                ))

    await session.flush()
    return factors


async def register_part(
    session: AsyncSession, tenant_id: uuid.UUID, *, vin: str, serial: str,
    component_code: str | None,
) -> VehiclePart:
    vin = _norm(vin) or ""
    serial = _norm(serial) or ""
    existing = await session.scalar(
        select(VehiclePart).where(
            VehiclePart.tenant_id == tenant_id, VehiclePart.serial == serial
        )
    )
    if existing:
        existing.vin = vin
        existing.component_code = component_code
        existing.is_active = True
        await session.flush()
        return existing
    part = VehiclePart(
        tenant_id=tenant_id, vin=vin, serial=serial,
        component_code=component_code, is_active=True,
    )
    session.add(part)
    session.add(PartEvent(
        tenant_id=tenant_id, vin=vin, component_code=component_code, serial=serial,
        event_type=PartEventType.registered, note="Registered to vehicle.",
    ))
    await session.flush()
    return part
