"""Explainable, advisory risk engine.

This is a TRANSPARENT heuristic — not a black-box classifier and never a fraud
determination. Every point of the score decomposes into named, evidence-linked
factors a reviewer can inspect. Weights come from the tenant's tunable
FraudIndicatorDef catalog.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai import Detection, OcrResult, VlmAnalysis
from app.db.models.claim import Claim
from app.db.models.component import FraudIndicatorDef
from app.db.models.enums import OcrFieldType
from app.db.models.scoring import CompletenessCheck, RiskAssessment
from app.ml.postprocess import vin as vin_pp

MODEL_VERSION = "risk-heuristic-v1"
_SCALE = 10.0  # weight*confidence*scale per signal
_INCOMPLETE_THRESHOLD = 70.0


async def _weights(session: AsyncSession, tenant_id) -> dict[str, tuple[float, str]]:
    rows = await session.scalars(
        select(FraudIndicatorDef).where(
            FraudIndicatorDef.tenant_id == tenant_id, FraudIndicatorDef.is_active.is_(True)
        )
    )
    return {r.code: (r.default_weight, r.severity) for r in rows}


async def compute(
    session: AsyncSession, claim: Claim, completeness: CompletenessCheck | None
) -> RiskAssessment:
    weights = await _weights(session, claim.tenant_id)
    factors: list[dict] = []

    def add(indicator: str, confidence: float, evidence_refs: list[str], source: str):
        weight, severity = weights.get(indicator, (1.0, "medium"))
        contribution = round(weight * min(confidence, 1.0) * _SCALE, 2)
        factors.append({
            "indicator": indicator,
            "weight": weight,
            "severity": severity,
            "confidence": round(confidence, 2),
            "contribution": contribution,
            "evidence_refs": evidence_refs,
            "source": source,
        })

    # 1) YOLO defect detections — aggregate per defect type (best confidence).
    dets = list(
        await session.scalars(
            select(Detection).where(
                Detection.claim_id == claim.id, Detection.defect_label.is_not(None)
            )
        )
    )
    by_defect: dict[str, list[Detection]] = defaultdict(list)
    for d in dets:
        by_defect[d.defect_label].append(d)
    for defect, items in by_defect.items():
        best = max(items, key=lambda d: d.confidence)
        add(defect, best.confidence, [str(i.id) for i in items[:5]], "detection")

    # 2) VLM-observed damage (cross-modal corroboration).
    vlms = list(
        await session.scalars(select(VlmAnalysis).where(VlmAnalysis.claim_id == claim.id))
    )
    vlm_damage: dict[str, tuple[float, str]] = {}
    for va in vlms:
        for dmg in (va.findings or {}).get("visible_damage", []) or []:
            dtype = str(dmg.get("type", "")).strip()
            conf = float(dmg.get("confidence", 0.5) or 0.5)
            if dtype and dtype not in by_defect:  # avoid double counting with YOLO
                prev = vlm_damage.get(dtype, (0.0, ""))
                if conf > prev[0]:
                    vlm_damage[dtype] = (conf, str(va.id))
    for dtype, (conf, ref) in vlm_damage.items():
        add(dtype, conf * 0.8, [ref], "vlm")  # slightly discount single-modality

    # 3) VIN mismatch — high-value signal.
    vin_rows = list(
        await session.scalars(
            select(OcrResult).where(
                OcrResult.claim_id == claim.id, OcrResult.field_type == OcrFieldType.vin
            )
        )
    )
    if claim.vin and vin_rows:
        read = vin_rows[0].normalized_value or ""
        if read and read != claim.vin:
            add("vin_mismatch", 1.0, [str(vin_rows[0].id)], "ocr")
        elif read and not vin_pp.is_valid_vin(read):
            add("vin_invalid", 0.5, [str(vin_rows[0].id)], "ocr")

    # 4) Incomplete inspection.
    if completeness is not None and float(completeness.score) < _INCOMPLETE_THRESHOLD:
        deficit = (100.0 - float(completeness.score)) / 100.0
        add("incomplete_inspection", deficit, [str(completeness.id)], "completeness")

    # 5) Serial-number lifecycle (anti swap-and-sell). Tenant-tuned weights
    # override the defaults baked into the serial factors.
    from app.services import serial_service

    for sf in await serial_service.run_checks(session, claim):
        weight, severity = weights.get(sf["indicator"], (sf["weight"], sf["severity"]))
        sf["weight"], sf["severity"] = weight, severity
        sf["contribution"] = round(weight * min(sf["confidence"], 1.0) * _SCALE, 2)
        factors.append(sf)

    # 6) Battery health (from an attached BatteryOS report, if any).
    from app.services import battery_service

    report = await battery_service.get_for_claim(session, claim.id)
    if report is not None:
        for bf in battery_service.risk_factors(report):
            weight, severity = weights.get(bf["indicator"], (bf["weight"], bf["severity"]))
            bf["weight"], bf["severity"] = weight, severity
            bf["contribution"] = round(weight * min(bf["confidence"], 1.0) * _SCALE, 2)
            factors.append(bf)

    # 7) Non-battery telemetry history (motor/controller/usage/safety), by VIN.
    from app.services import telemetry_service

    for tf in await telemetry_service.risk_factors_for_claim(session, claim.tenant_id, claim.vin):
        weight, severity = weights.get(tf["indicator"], (tf["weight"], tf["severity"]))
        tf["weight"], tf["severity"] = weight, severity
        tf["contribution"] = round(weight * min(tf["confidence"], 1.0) * _SCALE, 2)
        factors.append(tf)

    raw = sum(f["contribution"] for f in factors)
    score = round(min(100.0, raw), 2)
    factors.sort(key=lambda f: f["contribution"], reverse=True)

    rationale = _rationale(score, factors)

    assessment = RiskAssessment(
        tenant_id=claim.tenant_id,
        claim_id=claim.id,
        score=score,
        factors=factors,
        rationale=rationale,
        model_version=MODEL_VERSION,
    )
    session.add(assessment)
    claim.risk_score = score
    await session.flush()
    return assessment


def _rationale(score: float, factors: list[dict]) -> str:
    if not factors:
        return (
            "No risk indicators were detected from the available evidence. "
            "Advisory only — the reviewer makes the final decision."
        )
    top = factors[:3]
    parts = ", ".join(
        f"{f['indicator'].replace('_', ' ')} ({f['source']}, "
        f"{int(f['confidence'] * 100)}% conf)"
        for f in top
    )
    band = "low" if score < 33 else "elevated" if score < 66 else "high"
    return (
        f"Advisory risk score {score}/100 ({band}). Top contributing indicators: "
        f"{parts}. These are evidence-linked observations, not a fraud "
        f"determination — the reviewer makes the final decision."
    )
