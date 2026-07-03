"""Unified defect-vs-abuse warranty verdict.

Synthesizes every source already computed for a claim — physical inspection
(YOLO/VLM), serial-number integrity, battery health (BatteryOS), and vehicle
telemetry — into ONE advisory recommendation with a transparent per-source
breakdown. It is advisory only: the reviewer makes the final warranty decision.

Axis convention: negative = points to a genuine manufacturing DEFECT (supports
warranty); positive = points to MISUSE / EXTERNAL cause (warranty weaker).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.claim import Claim
from app.db.models.scoring import RiskAssessment
from app.services import battery_service, telemetry_service

# Map a per-source "leaning" string to an axis value.
_LEAN_AXIS = {
    "supports_warranty": -1.0,
    "suggests_misuse": 1.0,
    "external_cause": 1.2,
    "inconclusive": 0.0,
    "no_data": 0.0,
}

# Inspection damage types that indicate an EXTERNAL / abuse cause (vs a latent defect).
_EXTERNAL_DAMAGE = {
    "impact_dent", "impact_damage", "broken", "water_stain", "water_ingress",
    "tamper_mark", "missing_seal", "opened_enclosure", "non_standard_mod",
}

# Source weights.
_W_BATTERY = 1.0
_W_TELEMETRY = 1.0
_W_INSPECTION = 0.6

_DECISION_BAND = 0.34  # |normalized score| beyond this gives a directional verdict


def _inspection_leaning(risk: RiskAssessment | None) -> tuple[str, list[str]]:
    """Derive an inspection leaning from the latest risk factors."""
    if risk is None:
        return "no_data", []
    ext = [
        f for f in (risk.factors or [])
        if f.get("source") in ("detection", "vlm")
        and any(k in (f.get("indicator") or "") for k in _EXTERNAL_DAMAGE)
    ]
    if ext:
        return "external_cause", [f["indicator"] for f in ext]
    has_damage = any(f.get("source") in ("detection", "vlm") for f in (risk.factors or []))
    return ("inconclusive" if has_damage else "no_data"), []


def _serial_integrity(risk: RiskAssessment | None) -> list[dict]:
    if risk is None:
        return []
    return [f for f in (risk.factors or []) if f.get("source") == "serial"]


async def compute(session: AsyncSession, claim: Claim) -> dict:
    risk = await session.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.claim_id == claim.id)
        .order_by(RiskAssessment.created_at.desc())
    )

    sources: list[dict] = []

    # 1) Battery (BatteryOS BHR)
    report = await battery_service.get_for_claim(session, claim.id)
    if report is not None and report.warranty_leaning:
        sources.append({
            "source": "battery", "leaning": report.warranty_leaning,
            "weight": _W_BATTERY, "note": report.assessment_note,
        })

    # 2) Telemetry (by VIN)
    if claim.vin:
        tel = await telemetry_service.assess(session, claim.tenant_id, claim.vin)
        if tel.get("summary"):
            sources.append({
                "source": "telemetry", "leaning": tel["leaning"],
                "weight": _W_TELEMETRY, "note": tel["note"],
            })

    # 3) Inspection (physical damage)
    insp_lean, insp_types = _inspection_leaning(risk)
    if insp_lean != "no_data":
        note = (
            f"External-cause damage detected ({', '.join(insp_types)})."
            if insp_lean == "external_cause"
            else "Physical damage detected; cause not determinable from imagery alone."
        )
        sources.append({
            "source": "inspection", "leaning": insp_lean,
            "weight": _W_INSPECTION, "note": note,
        })

    # Weighted vote.
    total_w = 0.0
    score = 0.0
    for s in sources:
        axis = _LEAN_AXIS.get(s["leaning"], 0.0)
        s["contribution"] = round(axis * s["weight"], 3)
        score += axis * s["weight"]
        total_w += s["weight"]
    norm = (score / total_w) if total_w else 0.0

    if not sources:
        verdict = "insufficient_data"
    elif norm <= -_DECISION_BAND:
        verdict = "likely_manufacturing_defect"
    elif norm >= _DECISION_BAND:
        verdict = "likely_misuse_or_external"
    else:
        verdict = "inconclusive"

    confidence = round(min(1.0, abs(norm)), 2)

    integrity = _serial_integrity(risk)
    integrity_concern = bool(integrity)

    return {
        "verdict": verdict,
        "confidence": confidence,
        "score": round(norm, 3),
        "sources": sources,
        "integrity_concern": integrity_concern,
        "integrity_notes": [f.get("note") for f in integrity if f.get("note")],
        "rationale": _rationale(verdict, sources, integrity_concern),
        "disclaimer": (
            "Advisory only — a synthesis of available evidence to assist the reviewer. "
            "It is not a warranty decision and never alleges fraud."
        ),
    }


def _rationale(verdict: str, sources: list[dict], integrity: bool) -> str:
    label = {
        "likely_manufacturing_defect": "Evidence leans toward a genuine manufacturing defect (supports the warranty claim)",
        "likely_misuse_or_external": "Evidence leans toward misuse or external cause (warranty support is weaker)",
        "inconclusive": "Evidence is mixed; no clear lean",
        "insufficient_data": "Not enough evidence attached to form a view",
    }.get(verdict, verdict)
    parts = [
        f"{s['source']}: {s['leaning'].replace('_', ' ')}"
        for s in sources
    ]
    base = f"{label}. Sources — {', '.join(parts)}." if parts else label + "."
    if integrity:
        base += (
            " NOTE: serial-number integrity concerns were flagged — verify the claimed "
            "parts independently."
        )
    return base + " The reviewer makes the final decision."
