"""Evidence completeness: compare what the inspection template requires against
what was actually captured/extracted. Produces an actionable missing-evidence
list — the most useful artifact for the mechanic."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai import OcrResult, Transcript
from app.db.models.claim import Claim
from app.db.models.enums import MediaKind, OcrFieldType
from app.db.models.inspection_template import InspectionTemplate
from app.db.models.media import Frame, MediaAsset
from app.db.models.scoring import CompletenessCheck
from app.ml.postprocess import vin as vin_pp


async def compute(session: AsyncSession, claim: Claim) -> CompletenessCheck:
    template = None
    if claim.template_id:
        template = await session.get(InspectionTemplate, claim.template_id)
    req_views = list(template.required_views) if template else []
    req_evidence = dict(template.required_evidence) if template else {}

    n_images = await session.scalar(
        select(func.count()).select_from(MediaAsset).where(
            MediaAsset.claim_id == claim.id, MediaAsset.kind == MediaKind.image
        )
    ) or 0
    n_frames = await session.scalar(
        select(func.count()).select_from(Frame).where(Frame.claim_id == claim.id)
    ) or 0
    n_media = await session.scalar(
        select(func.count()).select_from(MediaAsset).where(MediaAsset.claim_id == claim.id)
    ) or 0
    visual_units = n_images + n_frames

    vin_rows = list(
        await session.scalars(
            select(OcrResult).where(
                OcrResult.claim_id == claim.id, OcrResult.field_type == OcrFieldType.vin
            )
        )
    )
    has_valid_vin = any(
        r.normalized_value and vin_pp.is_valid_vin(r.normalized_value) for r in vin_rows
    )
    transcript = await session.scalar(
        select(Transcript).where(Transcript.claim_id == claim.id)
    )
    has_narration = bool(
        (transcript and transcript.full_text.strip()) or claim.mechanic_narrative
    )

    # Build checks (only those the template requires, plus a baseline).
    checks: list[tuple[str, bool, str]] = []  # (key, present, human_label)
    checks.append(("media_present", n_media > 0, "At least one piece of evidence"))

    if req_evidence.get("min_images"):
        need = int(req_evidence["min_images"])
        checks.append(
            (f"min_images>={need}", visual_units >= need, f"At least {need} images/frames")
        )
    if req_evidence.get("vin"):
        checks.append(("vin_readable", has_valid_vin, "A readable, valid VIN"))
    if req_evidence.get("audio_narration"):
        checks.append(("audio_narration", has_narration, "Spoken/written narration"))
    if req_views:
        # Proxy: require at least as many distinct visual units as required views.
        ok = visual_units >= len(req_views)
        checks.append(
            ("view_coverage", ok, f"Coverage for {len(req_views)} required views")
        )

    present = {k: ok for k, ok, _ in checks}
    missing = [label for _, ok, label in checks if not ok]
    score = round(100.0 * sum(present.values()) / len(checks), 2) if checks else 0.0

    check = CompletenessCheck(
        tenant_id=claim.tenant_id,
        claim_id=claim.id,
        template_id=claim.template_id,
        required={"views": req_views, "evidence": req_evidence},
        present=present,
        missing=missing,
        score=score,
    )
    session.add(check)
    claim.completeness_score = score
    await session.flush()
    return check
