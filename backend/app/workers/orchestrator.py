"""Pipeline orchestration.

Stages: frame_extraction → (AI fan-out: detection → vlm/ocr on keyframes,
asr, embeddings) → scoring → ready_for_review.

Each stage runs in its OWN DB session (fresh connection) so a long blocking
ML call or a stage failure can't poison the connection used by later stages.
At GPU scale these AI stages become a Celery chord across the "gpu" queue.
"""
from __future__ import annotations

import tempfile
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.claim import Claim
from app.db.models.enums import ClaimStatus, JobStatus, MediaKind, MediaStatus
from app.db.models.media import Frame, MediaAsset
from app.db.models.processing_job import ProcessingJob
from app.db.session import SessionLocal
from app.services import (
    completeness_service,
    report_service,
    risk_service,
    storage_service,
)
from app.workers import ai_stages, media_processing
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

log = get_logger(__name__)

StageWork = Callable[[AsyncSession, Claim], Awaitable[tuple]]


def enqueue_pipeline(claim_id: str) -> None:
    run_pipeline.delay(claim_id)


@celery_app.task(name="app.workers.orchestrator.run_pipeline", bind=True, max_retries=2)
def run_pipeline(self, claim_id: str) -> dict:
    return run_async(_process_claim(uuid.UUID(claim_id), self.request.id))


async def _record_stage(
    claim_id: uuid.UUID, task_id: str | None, stage: str, work: StageWork
) -> tuple | None:
    """Run one stage in its own session, recording a ProcessingJob. Tolerant of
    failure (partial pipeline) — returns the stage result or None on error."""
    async with SessionLocal() as session:
        claim = await session.get(Claim, claim_id)
        job = ProcessingJob(
            claim_id=claim_id, celery_task_id=task_id, stage=stage,
            status=JobStatus.running, started_at=datetime.now(UTC),
        )
        session.add(job)
        await session.flush()
        try:
            result = await work(session, claim)
            job.status = JobStatus.succeeded if result[0] else JobStatus.skipped
            job.finished_at = datetime.now(UTC)
            job.metrics = {"items": result[1]}
            await session.commit()
            return result
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            async with SessionLocal() as s2:
                s2.add(ProcessingJob(
                    claim_id=claim_id, celery_task_id=task_id, stage=stage,
                    status=JobStatus.failed, finished_at=datetime.now(UTC),
                    error=str(exc)[:1000],
                ))
                await s2.commit()
            log.warning("stage failed (continuing)", stage=stage, error=str(exc)[:200])
            return None


async def _process_claim(claim_id: uuid.UUID, task_id: str | None) -> dict:
    async with SessionLocal() as s:
        claim = await s.get(Claim, claim_id)
        if claim is None:
            return {"error": "claim not found"}
        claim.status = ClaimStatus.processing
        await s.commit()

    # Stage 1: frame extraction (critical).
    fe = await _record_stage(claim_id, task_id, "frame_extraction", _frame_extraction)
    if fe is None:
        async with SessionLocal() as s:
            c = await s.get(Claim, claim_id)
            c.status = ClaimStatus.failed
            c.processing_error = "frame extraction failed"
            await s.commit()
        return {"error": "frame_extraction failed"}

    metrics: dict = {}
    # Detection + keyframe-gated VLM/OCR need the downloaded images (workdir).
    with tempfile.TemporaryDirectory() as workdir:
        async with SessionLocal() as s:
            claim = await s.get(Claim, claim_id)
            units = await ai_stages.build_image_units(s, claim, workdir)

        det = await _record_stage(
            claim_id, task_id, "detection",
            lambda se, cl: ai_stages.run_detection(se, cl, units),
        )
        metrics["detections"] = det[1] if det else 0
        defect_keys = det[2] if det and len(det) > 2 else set()

        keyframes = ai_stages.select_keyframes(units, defect_keys, settings.vlm_max_keyframes)
        async with SessionLocal() as s:
            await ai_stages.mark_keyframes(s, keyframes)
            await s.commit()

        vlm = await _record_stage(
            claim_id, task_id, "vlm",
            lambda se, cl: ai_stages.run_vlm(se, cl, keyframes),
        )
        metrics["vlm"] = vlm[1] if vlm else 0
        ocr = await _record_stage(
            claim_id, task_id, "ocr",
            lambda se, cl: ai_stages.run_ocr(se, cl, keyframes),
        )
        metrics["ocr"] = ocr[1] if ocr else 0

    asr = await _record_stage(claim_id, task_id, "asr", ai_stages.run_asr)
    metrics["asr"] = asr[1] if asr else 0
    emb = await _record_stage(claim_id, task_id, "embeddings", ai_stages.run_embeddings)
    metrics["embeddings"] = emb[1] if emb else 0
    await _record_stage(claim_id, task_id, "scoring", _scoring)

    async with SessionLocal() as s:
        c = await s.get(Claim, claim_id)
        c.status = ClaimStatus.ready_for_review
        c.processed_at = datetime.now(UTC)
        await s.commit()
    log.info("pipeline complete", claim_id=str(claim_id), **metrics)
    return metrics


async def _scoring(session: AsyncSession, claim: Claim) -> tuple[bool, int]:
    completeness = await completeness_service.compute(session, claim)
    await risk_service.compute(session, claim, completeness)
    await report_service.generate(session, claim)
    return True, 1


# --- frame extraction --------------------------------------------------------
async def _frame_extraction(session: AsyncSession, claim: Claim) -> tuple[bool, int]:
    assets = list(
        await session.scalars(
            select(MediaAsset).where(
                MediaAsset.claim_id == claim.id,
                MediaAsset.status == MediaStatus.uploaded,
            )
        )
    )
    total = 0
    for asset in assets:
        if asset.kind == MediaKind.video:
            total += await _ingest_video(session, claim, asset)
        else:
            await _ingest_image(asset)
        asset.status = MediaStatus.processed
    await session.flush()
    return True, total


async def _ingest_video(session: AsyncSession, claim: Claim, asset: MediaAsset) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        video_path = str(Path(tmp) / "input")
        storage_service.download_to(asset.s3_key, video_path)

        meta = media_processing.probe(video_path)
        asset.duration_s = meta.duration_s
        asset.width = meta.width
        asset.height = meta.height

        frames = media_processing.extract_frames(video_path, str(Path(tmp) / "frames"))
        for f in frames:
            frame_id = uuid.uuid4()
            key = f"tenants/{claim.tenant_id}/claims/{claim.id}/frames/{frame_id}.jpg"
            storage_service.upload_file(f.local_path, key, content_type="image/jpeg")
            session.add(
                Frame(
                    id=frame_id, tenant_id=claim.tenant_id, claim_id=claim.id,
                    media_asset_id=asset.id, s3_key=key, timestamp_s=f.timestamp_s,
                    frame_index=f.frame_index, sharpness=f.sharpness, is_keyframe=False,
                )
            )
        return len(frames)


async def _ingest_image(asset: MediaAsset) -> None:
    import io

    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        local = str(Path(tmp) / "img")
        try:
            storage_service.download_to(asset.s3_key, local)
            with Image.open(io.BytesIO(Path(local).read_bytes())) as im:
                asset.width, asset.height = im.size
        except Exception:  # noqa: BLE001
            pass
