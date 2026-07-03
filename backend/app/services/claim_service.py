from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.db.models.claim import Claim
from app.db.models.enums import ClaimStatus, MediaStatus, UserRole
from app.db.models.media import MediaAsset
from app.db.models.user import User
from app.schemas.claim import ClaimCreate, ClaimUpdate

log = get_logger(__name__)


def _generate_claim_number() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")
    return f"CLM-{today}-{secrets.token_hex(3).upper()}"


async def create_claim(session: AsyncSession, current: User, data: ClaimCreate) -> Claim:
    claim = Claim(
        tenant_id=current.tenant_id,
        claim_number=_generate_claim_number(),
        created_by_user_id=current.id,
        status=ClaimStatus.draft,
        **data.model_dump(),
    )
    session.add(claim)
    await session.flush()
    return claim


async def get_claim(session: AsyncSession, tenant_id: uuid.UUID, claim_id: uuid.UUID) -> Claim:
    claim = await session.scalar(
        select(Claim).where(Claim.id == claim_id, Claim.tenant_id == tenant_id)
    )
    if claim is None:
        raise NotFoundError("Claim not found")
    return claim


async def list_claims(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    page: int,
    size: int,
    status: ClaimStatus | None = None,
    vin: str | None = None,
    reviewer_id: uuid.UUID | None = None,
) -> tuple[list[Claim], int]:
    stmt = select(Claim).where(Claim.tenant_id == tenant_id)
    if status is not None:
        stmt = stmt.where(Claim.status == status)
    if vin:
        stmt = stmt.where(Claim.vin == vin.strip().upper())
    if reviewer_id is not None:
        stmt = stmt.where(Claim.assigned_reviewer_id == reviewer_id)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(Claim.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def update_claim(session: AsyncSession, claim: Claim, data: ClaimUpdate) -> Claim:
    if claim.status != ClaimStatus.draft:
        raise ConflictError("Only draft claims can be edited")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(claim, k, v)
    await session.flush()
    return claim


async def assign_reviewer(
    session: AsyncSession, claim: Claim, reviewer_id: uuid.UUID
) -> Claim:
    reviewer = await session.scalar(
        select(User).where(
            User.id == reviewer_id, User.tenant_id == claim.tenant_id
        )
    )
    if reviewer is None:
        raise NotFoundError("Reviewer not found")
    if reviewer.role not in (UserRole.reviewer, UserRole.admin):
        raise PermissionDeniedError("Assignee must be a reviewer or admin")
    claim.assigned_reviewer_id = reviewer_id
    await session.flush()
    return claim


async def submit_claim(session: AsyncSession, claim: Claim) -> Claim:
    if claim.status not in (ClaimStatus.draft, ClaimStatus.needs_more_evidence):
        raise ConflictError(f"Cannot submit a claim in status '{claim.status.value}'")

    uploaded = await session.scalar(
        select(func.count())
        .select_from(MediaAsset)
        .where(
            MediaAsset.claim_id == claim.id,
            MediaAsset.status == MediaStatus.uploaded,
        )
    )
    if not uploaded:
        raise ConflictError("Upload at least one piece of evidence before submitting")

    claim.status = ClaimStatus.queued
    claim.submitted_at = datetime.now(UTC)
    claim.processing_error = None
    await session.flush()

    # Enqueue the pipeline. Lazy import keeps Celery out of the request path import graph.
    from app.workers.orchestrator import enqueue_pipeline

    enqueue_pipeline(str(claim.id))
    log.info("claim submitted", claim_id=str(claim.id), number=claim.claim_number)
    return claim
