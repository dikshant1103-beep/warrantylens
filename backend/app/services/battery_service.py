"""Battery Health Report ingestion + defect-vs-abuse assessment.

WarrantyLens reads a BHR (produced by BatteryOS), stores it against a claim, and
derives an ADVISORY warranty leaning + risk factors. Transparent/heuristic — the
reviewer still decides. Battery health alone never approves or rejects a claim.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.battery import BatteryReport
from app.db.models.claim import Claim
from app.schemas.battery import BatteryHealthReport

_SCALE = 10.0

# Abuse-signature indicators (battery context) and their advisory weights.
_ABUSE_WEIGHTS = {
    "frequent_hot_fast_charge": 2.5,
    "over_temp_charge": 2.5,
    "deep_discharge": 2.0,
    "overcurrent": 2.0,
    "high_dc_fast_charge": 1.5,
    "harsh_usage": 1.5,
}
_SOH_LOW = 70.0  # below this SoH the pack is genuinely degraded


def ingest(claim: Claim, bhr: BatteryHealthReport) -> BatteryReport:
    """Build a BatteryReport row from a parsed BHR (caller adds + commits)."""
    leaning, note = _assess(bhr)
    return BatteryReport(
        tenant_id=claim.tenant_id,
        claim_id=claim.id,
        source=bhr.source,
        schema_version=bhr.schema_version,
        generated_at=bhr.generated_at,
        vin=bhr.vehicle.vin,
        pack_id=bhr.vehicle.pack_id,
        chemistry=bhr.chemistry,
        soh_percent=bhr.soh_percent,
        rul_cycles=bhr.rul.cycles,
        rul_ci_low=bhr.rul.ci_low,
        rul_ci_high=bhr.rul.ci_high,
        capacity_fade_percent=bhr.capacity_fade_percent,
        charging=bhr.charging,
        faults=[f.model_dump() for f in bhr.faults],
        abuse_indicators=list(bhr.abuse_indicators),
        payload=bhr.model_dump(mode="json"),
        warranty_leaning=leaning,
        assessment_note=note,
    )


def _assess(bhr: BatteryHealthReport) -> tuple[str, str]:
    """Defect-vs-abuse leaning from battery signals.

    - Abuse signatures present  -> suggests_misuse (warranty weaker)
    - Degraded SoH with NO abuse -> supports_warranty (looks like a genuine defect)
    - Otherwise                  -> inconclusive
    """
    abuse = [a for a in bhr.abuse_indicators if a in _ABUSE_WEIGHTS]
    high_faults = [f for f in bhr.faults if (f.severity or "").lower() == "high"]
    soh = bhr.soh_percent

    if abuse:
        return (
            "suggests_misuse",
            f"Battery telemetry shows abuse signatures ({', '.join(abuse)}). "
            f"Failure may stem from usage rather than a manufacturing defect — advisory only.",
        )
    if soh is not None and soh < _SOH_LOW:
        return (
            "supports_warranty",
            f"State-of-health is low ({soh:.0f}%) with no abuse signatures detected — "
            f"consistent with a genuine battery defect rather than misuse.",
        )
    if high_faults:
        return (
            "inconclusive",
            f"{len(high_faults)} high-severity fault(s) logged; no clear abuse pattern. "
            f"Reviewer judgement needed.",
        )
    return (
        "inconclusive",
        "Battery telemetry shows no abuse signatures and health is within normal range.",
    )


def risk_factors(report: BatteryReport) -> list[dict]:
    """Battery-derived risk factors for the explainable risk engine."""
    factors: list[dict] = []

    def add(indicator: str, weight: float, confidence: float, note: str):
        factors.append({
            "indicator": indicator, "weight": weight, "severity": "high",
            "confidence": round(min(confidence, 1.0), 2),
            "contribution": round(weight * min(confidence, 1.0) * _SCALE, 2),
            "evidence_refs": [str(report.id)], "source": "battery", "note": note,
        })

    for a in report.abuse_indicators or []:
        w = _ABUSE_WEIGHTS.get(a)
        if w:
            add(f"battery_{a}", w, 0.9, f"Battery telemetry: {a.replace('_', ' ')}.")

    for f in report.faults or []:
        if (f.get("severity") or "").lower() == "high":
            add("battery_fault_high", 1.5, 0.7,
                f"High-severity battery fault {f.get('code', '')}.")

    return factors


async def get_for_claim(session: AsyncSession, claim_id) -> BatteryReport | None:
    return await session.scalar(
        select(BatteryReport)
        .where(BatteryReport.claim_id == claim_id)
        .order_by(BatteryReport.created_at.desc())
    )
