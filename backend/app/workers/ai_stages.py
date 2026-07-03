"""AI pipeline stages. Each is independent and tolerant: if its model is not
enabled/available the stage is skipped (not failed). Cost-tiered per
ARCHITECTURE.md §8.2 — detection on all image units, OCR/VLM only on keyframes.

An "image unit" is the AI's atom: either a frame extracted from video, or an
uploaded image asset (so image-only claims are analyzed too).
"""
from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.ai import (
    Detection,
    EmbeddingIndex,
    OcrResult,
    Transcript,
    VlmAnalysis,
)
from app.db.models.claim import Claim
from app.db.models.enums import MediaKind, OcrFieldType
from app.db.models.media import Frame, MediaAsset
from app.ml.clients import asr as asr_client
from app.ml.clients import detection as det_client
from app.ml.clients import embeddings as emb_client
from app.ml.clients import ocr as ocr_client
from app.ml.clients import vlm as vlm_client
from app.ml.postprocess import vin as vin_pp
from app.ml.prompts.inspection import get_prompt
from app.services import storage_service

log = get_logger(__name__)


@dataclass
class ImageUnit:
    s3_key: str
    local_path: str | None = None
    frame_id: uuid.UUID | None = None
    media_asset_id: uuid.UUID | None = None
    sharpness: float = 0.0


async def build_image_units(
    session: AsyncSession, claim: Claim, workdir: str
) -> list[ImageUnit]:
    """Video frames + uploaded image assets, downloaded once to workdir."""
    units: list[ImageUnit] = []
    frames = list(
        await session.scalars(select(Frame).where(Frame.claim_id == claim.id))
    )
    for fr in frames:
        units.append(
            ImageUnit(s3_key=fr.s3_key, frame_id=fr.id,
                      media_asset_id=fr.media_asset_id, sharpness=fr.sharpness or 0.0)
        )
    images = list(
        await session.scalars(
            select(MediaAsset).where(
                MediaAsset.claim_id == claim.id, MediaAsset.kind == MediaKind.image
            )
        )
    )
    for asset in images:
        units.append(ImageUnit(s3_key=asset.s3_key, media_asset_id=asset.id))

    for i, u in enumerate(units):
        local = str(Path(workdir) / f"unit_{i}.jpg")
        try:
            storage_service.download_to(u.s3_key, local)
            u.local_path = local
        except Exception as exc:  # noqa: BLE001
            log.warning("unit download failed", s3_key=u.s3_key, error=str(exc))
    return [u for u in units if u.local_path]


# --- Detection (all units) ---------------------------------------------------
async def run_detection(
    session: AsyncSession, claim: Claim, units: list[ImageUnit]
) -> tuple[bool, int, set]:
    det = det_client.get_detector()
    if det is None:
        return False, 0, set()
    count = 0
    defect_keys: set = set()
    for u in units:
        for d in det.detect(u.local_path):
            session.add(
                Detection(
                    tenant_id=claim.tenant_id, claim_id=claim.id, frame_id=u.frame_id,
                    media_asset_id=u.media_asset_id, model_version=settings.yolo_weights,
                    component_label=d.component_label, defect_label=d.defect_label,
                    confidence=d.confidence, bbox=d.bbox, severity=d.severity,
                )
            )
            count += 1
            if d.defect_label:
                defect_keys.add(u.frame_id or u.media_asset_id)
    await session.flush()
    return True, count, defect_keys


def select_keyframes(units: list[ImageUnit], defect_keys: set, limit: int) -> list[ImageUnit]:
    """Prioritize units with detected defects, then sharpest; cap at limit."""
    def score(u: ImageUnit) -> tuple[int, float]:
        key = u.frame_id or u.media_asset_id
        return (1 if key in defect_keys else 0, u.sharpness)

    return sorted(units, key=score, reverse=True)[:limit]


async def mark_keyframes(session: AsyncSession, keyframes: list[ImageUnit]) -> None:
    ids = [u.frame_id for u in keyframes if u.frame_id]
    if ids:
        for fr in await session.scalars(select(Frame).where(Frame.id.in_(ids))):
            fr.is_keyframe = True
        await session.flush()


# --- VLM (keyframes only) ----------------------------------------------------
async def run_vlm(
    session: AsyncSession, claim: Claim, keyframes: list[ImageUnit]
) -> tuple[bool, int]:
    vlm = vlm_client.get_vlm()
    if vlm is None:
        return False, 0
    prompt = get_prompt(settings.vlm_prompt_version)
    count = 0
    for u in keyframes:
        try:
            res = vlm.describe_image(Path(u.local_path).read_bytes(), prompt)
        except Exception as exc:  # noqa: BLE001
            log.warning("vlm unit failed", error=str(exc))
            continue
        session.add(
            VlmAnalysis(
                tenant_id=claim.tenant_id, claim_id=claim.id, frame_id=u.frame_id,
                media_asset_id=u.media_asset_id,
                prompt_version=settings.vlm_prompt_version, model_version=res.model_version,
                description=res.description, findings=res.findings,
                raw_response=res.raw_response,
            )
        )
        count += 1
    await session.flush()
    return True, count


# --- OCR (keyframes) + VIN/serial parsing ------------------------------------
async def run_ocr(
    session: AsyncSession, claim: Claim, keyframes: list[ImageUnit]
) -> tuple[bool, int]:
    ocr = ocr_client.get_ocr()
    if ocr is None:
        return False, 0
    all_text: list[str] = []
    count = 0
    for u in keyframes:
        for tok in ocr.read(u.local_path):
            all_text.append(tok.text)
            session.add(
                OcrResult(
                    tenant_id=claim.tenant_id, claim_id=claim.id, frame_id=u.frame_id,
                    media_asset_id=u.media_asset_id, field_type=OcrFieldType.label,
                    raw_text=tok.text, normalized_value=tok.text.strip().upper(),
                    confidence=tok.confidence, bbox=tok.bbox, model_version="paddleocr",
                )
            )
            count += 1

    joined = " ".join(all_text)
    vins = vin_pp.extract_vin_candidates(joined)
    if vins:
        best = vins[0]
        session.add(
            OcrResult(
                tenant_id=claim.tenant_id, claim_id=claim.id, field_type=OcrFieldType.vin,
                raw_text=best, normalized_value=best,
                confidence=1.0 if vin_pp.is_valid_vin(best) else 0.5,
                model_version="vin-parser",
            )
        )
        count += 1
    for serial in vin_pp.extract_serials(joined, exclude=set(vins))[:10]:
        session.add(
            OcrResult(
                tenant_id=claim.tenant_id, claim_id=claim.id, field_type=OcrFieldType.serial,
                raw_text=serial, normalized_value=serial, confidence=0.5,
                model_version="serial-parser",
            )
        )
        count += 1
    await session.flush()
    return True, count


# --- ASR (one pass per video) ------------------------------------------------
async def run_asr(session: AsyncSession, claim: Claim) -> tuple[bool, int]:
    asr = asr_client.get_asr()
    if asr is None:
        return False, 0
    videos = list(
        await session.scalars(
            select(MediaAsset).where(
                MediaAsset.claim_id == claim.id, MediaAsset.kind == MediaKind.video
            )
        )
    )
    count = 0
    for asset in videos:
        with tempfile.TemporaryDirectory() as tmp:
            local = str(Path(tmp) / "media")
            try:
                storage_service.download_to(asset.s3_key, local)
                result = asr.transcribe(local)
            except Exception as exc:  # noqa: BLE001
                log.warning("asr failed", asset_id=str(asset.id), error=str(exc))
                continue
        session.add(
            Transcript(
                tenant_id=claim.tenant_id, claim_id=claim.id, media_asset_id=asset.id,
                language=result.language, full_text=result.full_text,
                segments=result.segments, model_version=result.model_version,
            )
        )
        count += 1
    await session.flush()
    return True, count


# --- Embeddings + Qdrant -----------------------------------------------------
async def run_embeddings(session: AsyncSession, claim: Claim) -> tuple[bool, int]:
    embedder = emb_client.get_embedder()
    vectors = emb_client.get_vectors()
    if embedder is None or vectors is None:
        return False, 0

    chunks: list[tuple[str, str, str]] = []
    if claim.claim_reason or claim.mechanic_narrative:
        chunks.append(
            (f"{claim.claim_reason or ''} {claim.mechanic_narrative or ''}".strip(),
             "claim", str(claim.id))
        )
    for tr in await session.scalars(
        select(Transcript).where(Transcript.claim_id == claim.id)
    ):
        if tr.full_text:
            chunks.append((tr.full_text, "transcript", str(tr.id)))
    for va in await session.scalars(
        select(VlmAnalysis).where(VlmAnalysis.claim_id == claim.id)
    ):
        if va.description:
            chunks.append((va.description, "vlm", str(va.id)))

    chunks = [c for c in chunks if c[0]]
    if not chunks:
        return True, 0

    vectors.ensure_collection()
    embs = embedder.embed([c[0] for c in chunks])
    payloads = [
        {"claim_id": str(claim.id), "tenant_id": str(claim.tenant_id),
         "source_type": st, "source_id": sid}
        for _, st, sid in chunks
    ]
    point_ids = vectors.upsert(embs, payloads)
    for (_, st, sid), pid in zip(chunks, point_ids, strict=True):
        session.add(
            EmbeddingIndex(
                tenant_id=claim.tenant_id, claim_id=claim.id, source_type=st,
                source_id=sid, qdrant_point_id=pid, model_version=settings.embed_model,
            )
        )
    await session.flush()
    return True, len(chunks)
