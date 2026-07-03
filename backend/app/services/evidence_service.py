from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.claim import Claim
from app.db.models.enums import MediaStatus
from app.db.models.media import Frame, MediaAsset
from app.schemas.media import UploadFileSpec
from app.services import storage_service


def _media_key(
    tenant_id: uuid.UUID, claim_id: uuid.UUID, asset_id: uuid.UUID, filename: str
) -> str:
    safe = filename.replace("/", "_").replace("..", "_")
    return f"tenants/{tenant_id}/claims/{claim_id}/media/{asset_id}/{safe}"


async def create_upload_slots(
    session: AsyncSession,
    claim: Claim,
    specs: list[UploadFileSpec],
    *,
    uploaded_by: uuid.UUID,
) -> list[tuple[MediaAsset, str]]:
    """Create pending MediaAsset rows and presigned PUT URLs."""
    out: list[tuple[MediaAsset, str]] = []
    for spec in specs:
        asset_id = uuid.uuid4()
        s3_key = _media_key(claim.tenant_id, claim.id, asset_id, spec.filename)
        asset = MediaAsset(
            id=asset_id,
            tenant_id=claim.tenant_id,
            claim_id=claim.id,
            kind=spec.kind,
            s3_key=s3_key,
            content_type=spec.content_type,
            size_bytes=spec.size,
            status=MediaStatus.pending,
            uploaded_by=uploaded_by,
        )
        session.add(asset)
        url = storage_service.presign_put(s3_key, spec.content_type)
        out.append((asset, url))
    await session.flush()
    return out


async def get_asset(
    session: AsyncSession, claim: Claim, asset_id: uuid.UUID
) -> MediaAsset:
    asset = await session.scalar(
        select(MediaAsset).where(
            MediaAsset.id == asset_id, MediaAsset.claim_id == claim.id
        )
    )
    if asset is None:
        raise NotFoundError("Media asset not found")
    return asset


async def complete_upload(
    session: AsyncSession, asset: MediaAsset, *, sha256: str | None
) -> MediaAsset:
    """Verify the object landed in S3, then mark uploaded."""
    meta = storage_service.head_object(asset.s3_key)
    if meta is None:
        raise ConflictError("Upload not found in storage; PUT may have failed")
    asset.size_bytes = meta.get("size_bytes") or asset.size_bytes
    if meta.get("content_type"):
        asset.content_type = meta["content_type"]
    if sha256:
        asset.sha256 = sha256
    asset.status = MediaStatus.uploaded
    await session.flush()
    return asset


async def list_evidence(
    session: AsyncSession, claim: Claim
) -> tuple[list[MediaAsset], list[Frame]]:
    # Only assets whose bytes actually landed in storage — never show 'pending'
    # slots (abandoned/failed uploads) as broken thumbnails.
    assets = list(
        await session.scalars(
            select(MediaAsset).where(
                MediaAsset.claim_id == claim.id,
                MediaAsset.status.in_([MediaStatus.uploaded, MediaStatus.processed]),
            )
        )
    )
    frames = list(
        await session.scalars(
            select(Frame).where(Frame.claim_id == claim.id).order_by(Frame.frame_index)
        )
    )
    return assets, frames


def with_url(s3_key: str) -> str:
    return storage_service.presign_get(s3_key)
