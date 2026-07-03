"""Inspection report generation. Assembles a structured, evidence-linked payload,
renders an HTML report, and (if WeasyPrint is available) a PDF. Reports are
versioned and regenerable — never silently overwritten.

Every damage/risk item deep-links to the evidence that produced it. The report
is explicitly advisory; it never states a warranty decision or alleges fraud.
"""
from __future__ import annotations

import html
import tempfile
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.ai import Detection, OcrResult, Transcript
from app.db.models.claim import Claim
from app.db.models.enums import OcrFieldType
from app.db.models.media import Frame
from app.db.models.scoring import CompletenessCheck, Report, RiskAssessment
from app.services import storage_service

log = get_logger(__name__)
DISCLAIMER = (
    "This report is an AI-generated aid for the warranty reviewer. It surfaces "
    "evidence and advisory risk indicators only. It does not make a warranty "
    "decision and does not allege fraud. The final decision rests with a human reviewer."
)


async def generate(session: AsyncSession, claim: Claim) -> Report:
    completeness = await session.scalar(
        select(CompletenessCheck)
        .where(CompletenessCheck.claim_id == claim.id)
        .order_by(CompletenessCheck.created_at.desc())
    )
    risk = await session.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.claim_id == claim.id)
        .order_by(RiskAssessment.created_at.desc())
    )
    defects = list(
        await session.scalars(
            select(Detection).where(
                Detection.claim_id == claim.id, Detection.defect_label.is_not(None)
            ).order_by(Detection.confidence.desc())
        )
    )
    vin_rows = list(
        await session.scalars(
            select(OcrResult).where(
                OcrResult.claim_id == claim.id,
                OcrResult.field_type.in_([OcrFieldType.vin, OcrFieldType.serial]),
            )
        )
    )
    transcript = await session.scalar(
        select(Transcript).where(Transcript.claim_id == claim.id)
    )
    keyframes = list(
        await session.scalars(
            select(Frame).where(Frame.claim_id == claim.id, Frame.is_keyframe.is_(True))
        )
    )

    from app.services import verdict_service

    verdict = await verdict_service.compute(session, claim)

    payload = {
        "header": {
            "claim_number": claim.claim_number,
            "vin": claim.vin,
            "status": claim.status.value,
            "reason": claim.claim_reason,
        },
        "verdict": verdict,
        "scores": {
            "completeness": float(completeness.score) if completeness else None,
            "risk": float(risk.score) if risk else None,
        },
        "damage_summary": [
            {"defect": d.defect_label, "confidence": round(d.confidence, 2),
             "component": d.component_label, "frame_id": str(d.frame_id) if d.frame_id else None}
            for d in defects[:50]
        ],
        "identifiers": [
            {"type": r.field_type.value, "value": r.normalized_value} for r in vin_rows
        ],
        "missing_evidence": completeness.missing if completeness else [],
        "transcript": transcript.full_text if transcript else None,
        "risk_panel": {
            "score": float(risk.score) if risk else None,
            "rationale": risk.rationale if risk else None,
            "factors": risk.factors if risk else [],
        },
        "disclaimer": DISCLAIMER,
    }
    summary = (risk.rationale if risk else "No risk assessment available.")

    # Versioning
    prev = await session.scalar(
        select(func.max(Report.version)).where(Report.claim_id == claim.id)
    )
    version = (prev or 0) + 1

    html_doc = _render_html(claim, payload, keyframes)
    report = Report(
        tenant_id=claim.tenant_id, claim_id=claim.id, summary=summary,
        payload=payload, version=version,
    )
    session.add(report)
    await session.flush()

    base = f"tenants/{claim.tenant_id}/claims/{claim.id}/reports/{report.id}"
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "report.html"
        html_path.write_text(html_doc, encoding="utf-8")
        try:
            storage_service.upload_file(str(html_path), f"{base}.html", "text/html")
            report.s3_key_html = f"{base}.html"
        except Exception as exc:  # noqa: BLE001
            log.warning("report html upload failed", error=str(exc))

        pdf_bytes = _render_pdf(html_doc)
        if pdf_bytes:
            pdf_path = Path(tmp) / "report.pdf"
            pdf_path.write_bytes(pdf_bytes)
            try:
                storage_service.upload_file(str(pdf_path), f"{base}.pdf", "application/pdf")
                report.s3_key_pdf = f"{base}.pdf"
            except Exception as exc:  # noqa: BLE001
                log.warning("report pdf upload failed", error=str(exc))

    await session.flush()
    return report


def _render_pdf(html_doc: str) -> bytes | None:
    try:
        from weasyprint import HTML
    except Exception:  # noqa: BLE001
        log.info("weasyprint unavailable; report is HTML-only")
        return None
    try:
        return HTML(string=html_doc).write_pdf()
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf render failed", error=str(exc))
        return None


def _render_html(claim: Claim, payload: dict, keyframes: list[Frame]) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(str(d['defect']))}</td><td>{int(d['confidence']*100)}%</td>"
        f"<td>{e(str(d.get('component') or '-'))}</td></tr>"
        for d in payload["damage_summary"]
    ) or "<tr><td colspan='3'>No damage indicators detected.</td></tr>"

    factors = "".join(
        f"<li><b>{e(str(f['indicator']))}</b> — {e(str(f['source']))}, "
        f"contribution {f['contribution']} (refs: {len(f['evidence_refs'])})</li>"
        for f in payload["risk_panel"]["factors"]
    ) or "<li>None</li>"

    missing = "".join(f"<li>{e(str(m))}</li>" for m in payload["missing_evidence"]) \
        or "<li>Nothing missing.</li>"

    thumbs = ""
    for f in keyframes[:8]:
        try:
            url = storage_service.presign_get(f.s3_key)
            thumbs += f"<img src='{e(url)}' style='height:90px;margin:3px;border:1px solid #ccc'/>"
        except Exception:  # noqa: BLE001
            pass

    sc = payload["scores"]
    v = payload.get("verdict", {})
    vlabel = str(v.get("verdict", "")).replace("_", " ")
    vbg = {
        "likely_manufacturing_defect": "#dcfce7;color:#166534",
        "likely_misuse_or_external": "#fee2e2;color:#991b1b",
    }.get(v.get("verdict"), "#f1f5f9;color:#334155")
    return f"""<!doctype html><html><head><meta charset='utf-8'>
<style>
 body{{font-family:Arial,sans-serif;color:#0f172a;margin:32px}}
 h1{{color:#0369a1;margin-bottom:0}} .muted{{color:#64748b}}
 table{{border-collapse:collapse;width:100%;margin:8px 0}}
 td,th{{border:1px solid #e2e8f0;padding:6px;text-align:left;font-size:13px}}
 .badge{{display:inline-block;padding:2px 8px;border-radius:9999px;background:#e0f2fe;color:#0369a1}}
 .verdict{{padding:12px;border-radius:8px;margin:12px 0;background:{vbg}}}
 .disc{{background:#fffbeb;border:1px solid #fde68a;padding:10px;border-radius:8px;font-size:12px;color:#92400e}}
</style></head><body>
 <h1>WarrantyLens Inspection Report</h1>
 <p class='muted'>Claim {e(claim.claim_number)} · VIN {e(claim.vin or '—')} ·
   Completeness {sc['completeness']}/100 · <span class='badge'>Risk {sc['risk']}/100</span></p>
 <div class='verdict'><b>Advisory verdict: {e(vlabel.title())}</b>
   (confidence {v.get('confidence', 0)})<br>{e(str(v.get('rationale', '')))}</div>
 <h3>Risk panel (advisory)</h3>
 <p>{e(str(payload['risk_panel']['rationale'] or ''))}</p>
 <ul>{factors}</ul>
 <h3>Damage summary</h3>
 <table><tr><th>Indicator</th><th>Confidence</th><th>Component</th></tr>{rows}</table>
 <h3>Missing evidence</h3><ul>{missing}</ul>
 <h3>Key frames</h3><div>{thumbs or 'None'}</div>
 <h3>Narration</h3><p class='muted'>{e(payload['transcript'] or '—')}</p>
 <p class='disc'>{e(payload['disclaimer'])}</p>
</body></html>"""
