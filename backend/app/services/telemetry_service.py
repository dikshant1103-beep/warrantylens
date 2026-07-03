"""Non-battery telemetry: generate/store history and derive defect-vs-abuse
signals for the warranty assessment. Transparent/heuristic — advisory only.
"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vehicle import TelemetrySnapshot, Vehicle
from app.ml import telemetry_sim
from app.ml.telemetry_sim import CTRL_OVERTEMP, MOTOR_OVERTEMP

_SCALE = 10.0


async def get_or_create_vehicle(
    session: AsyncSession, tenant_id: uuid.UUID, vin: str, profile: str | None = None
) -> Vehicle:
    vin = vin.strip().upper()
    v = await session.scalar(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.vin == vin)
    )
    if v is None:
        v = Vehicle(tenant_id=tenant_id, vin=vin, telemetry_profile=profile)
        session.add(v)
        await session.flush()
    elif profile:
        v.telemetry_profile = profile
        await session.flush()
    return v


async def simulate(
    session: AsyncSession, tenant_id: uuid.UUID, vin: str, *,
    profile: str = "normal", days: int = 180,
) -> int:
    """Generate + store a telemetry history for a vehicle (replaces existing)."""
    vin = vin.strip().upper()
    await get_or_create_vehicle(session, tenant_id, vin, profile)
    await session.execute(
        delete(TelemetrySnapshot).where(
            TelemetrySnapshot.tenant_id == tenant_id, TelemetrySnapshot.vin == vin
        )
    )
    rows = telemetry_sim.generate(vin, profile=profile, days=days)
    for r in rows:
        session.add(TelemetrySnapshot(tenant_id=tenant_id, **r))
    await session.flush()
    return len(rows)


async def _snapshots(session: AsyncSession, tenant_id: uuid.UUID, vin: str) -> list[TelemetrySnapshot]:
    return list(
        await session.scalars(
            select(TelemetrySnapshot)
            .where(TelemetrySnapshot.tenant_id == tenant_id, TelemetrySnapshot.vin == vin)
            .order_by(TelemetrySnapshot.day)
        )
    )


def _trend(values: list[float]) -> float:
    """Simple linear slope (per day) via least squares; 0 if too short."""
    n = len(values)
    if n < 5:
        return 0.0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(values) / n
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    return sum((xs[i] - mx) * (values[i] - my) for i in range(n)) / denom


def summarize(snaps: list[TelemetrySnapshot]) -> dict:
    if not snaps:
        return {}
    motor_overtemp = sum(1 for s in snaps if (s.motor_temp_max_c or 0) > MOTOR_OVERTEMP)
    ctrl_overtemp = sum(1 for s in snaps if (s.controller_temp_max_c or 0) > CTRL_OVERTEMP)
    harsh = sum((s.harsh_accel_count + s.harsh_brake_count) for s in snaps)
    overcurrent = sum(s.overcurrent_events for s in snaps)
    water = sum(s.water_ingress_trip for s in snaps)
    impact = sum(s.impact_event for s in snaps)
    motor_slope = _trend([s.motor_temp_avg_c or 0 for s in snaps])
    ctrl_slope = _trend([s.controller_temp_avg_c or 0 for s in snaps])
    return {
        "days": len(snaps),
        "odometer_km": round(snaps[-1].odometer_km, 0),
        "motor_overtemp_days": motor_overtemp,
        "controller_overtemp_days": ctrl_overtemp,
        "harsh_events": harsh,
        "overcurrent_events": overcurrent,
        "water_ingress_events": water,
        "impact_events": impact,
        "motor_temp_slope": round(motor_slope, 4),
        "controller_temp_slope": round(ctrl_slope, 4),
    }


_DRIFT_THRESHOLD = 0.05  # °C/day upward trend that signals a developing defect


def _is_behavioral_abuse(summary: dict) -> bool:
    """Abuse = driver behaviour: harsh driving and/or repeated over-current.
    (High temps alone are NOT abuse — they can be caused by a defect.)"""
    days = max(summary.get("days", 1), 1)
    return (
        summary.get("harsh_events", 0) > days * 4
        or summary.get("overcurrent_events", 0) > days * 0.3
    )


def _factors(summary: dict) -> list[dict]:
    factors: list[dict] = []
    if not summary:
        return factors

    def add(indicator, weight, confidence, note):
        factors.append({
            "indicator": indicator, "weight": weight, "severity": "high",
            "confidence": round(min(confidence, 1.0), 2),
            "contribution": round(weight * min(confidence, 1.0) * _SCALE, 2),
            "evidence_refs": [], "source": "telemetry", "note": note,
        })

    days = max(summary.get("days", 1), 1)
    behavioral = _is_behavioral_abuse(summary)

    # External-cause events always count.
    if summary.get("water_ingress_events", 0) > 0:
        add("telemetry_water_ingress", 2.5, 1.0,
            "Water-ingress sensor tripped — external cause indicator.")
    if summary.get("impact_events", 0) > 0:
        add("telemetry_impact", 2.5, 1.0,
            "Impact event recorded — external cause indicator.")

    # Behavioural abuse signals.
    if summary.get("harsh_events", 0) > days * 4:
        add("telemetry_harsh_usage", 1.5, 0.7,
            f"High harsh-driving event count ({summary['harsh_events']}).")
    if summary.get("overcurrent_events", 0) > days * 0.3:
        add("telemetry_overcurrent", 1.5, 0.7,
            f"Frequent over-current events ({summary['overcurrent_events']}).")

    # Over-temp only counts AS RISK when it co-occurs with abusive driving;
    # otherwise high/rising temps are treated as a defect signal (supports warranty),
    # so we do not penalise the claim.
    if behavioral:
        if summary.get("motor_overtemp_days", 0) > days * 0.1:
            add("telemetry_motor_overtemp", 2.0, 0.8,
                f"Motor over-temperature on {summary['motor_overtemp_days']} days under hard use.")
        if summary.get("controller_overtemp_days", 0) > days * 0.1:
            add("telemetry_controller_overtemp", 2.0, 0.8,
                f"Controller over-temperature on {summary['controller_overtemp_days']} days under hard use.")
    return factors


def leaning(summary: dict) -> tuple[str, str]:
    if not summary:
        return "no_data", "No telemetry history available for this vehicle."
    if summary.get("water_ingress_events", 0) or summary.get("impact_events", 0):
        return ("external_cause",
                "Telemetry logs a water-ingress/impact event — points to external damage, not a defect.")
    drift = max(summary.get("motor_temp_slope", 0), summary.get("controller_temp_slope", 0))
    if _is_behavioral_abuse(summary):
        return ("suggests_misuse",
                "Telemetry shows harsh-usage / over-current abuse signatures — failure may stem from usage.")
    if drift > _DRIFT_THRESHOLD:
        return ("supports_warranty",
                "A component's temperature trended abnormally upward with no abuse signature — "
                "consistent with a developing manufacturing defect.")
    return ("inconclusive", "Telemetry within normal ranges; no abuse or clear defect trend.")


async def assess(session: AsyncSession, tenant_id: uuid.UUID, vin: str) -> dict:
    """Full telemetry assessment for a VIN: summary + factors + leaning + series."""
    snaps = await _snapshots(session, tenant_id, vin)
    summary = summarize(snaps)
    lean, note = leaning(summary)
    # Downsample series for the UI (every ~7th day).
    step = max(len(snaps) // 60, 1)
    series = [
        {"day": s.day.isoformat(), "motor": s.motor_temp_avg_c, "controller": s.controller_temp_avg_c}
        for s in snaps[::step]
    ]
    return {
        "summary": summary, "factors": _factors(summary),
        "leaning": lean, "note": note, "series": series,
    }


async def risk_factors_for_claim(session: AsyncSession, tenant_id: uuid.UUID, vin: str | None) -> list[dict]:
    if not vin:
        return []
    snaps = await _snapshots(session, tenant_id, vin.strip().upper())
    if not snaps:
        return []
    return _factors(summarize(snaps))


async def has_telemetry(session: AsyncSession, tenant_id: uuid.UUID, vin: str) -> bool:
    n = await session.scalar(
        select(func.count()).select_from(TelemetrySnapshot).where(
            TelemetrySnapshot.tenant_id == tenant_id,
            TelemetrySnapshot.vin == vin.strip().upper(),
        )
    )
    return bool(n)
