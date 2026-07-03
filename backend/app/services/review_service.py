"""Human review workflow. The reviewer's decision is authoritative; the system
records it and transitions claim state. The system itself never decides."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.claim import Claim
from app.db.models.enums import ClaimStatus, ReviewDecision
from app.db.models.scoring import Review
from app.db.models.user import User

# Map a human decision to the resulting claim status.
_DECISION_STATUS = {
    ReviewDecision.approved: ClaimStatus.reviewed,
    ReviewDecision.rejected: ClaimStatus.reviewed,
    ReviewDecision.escalated: ClaimStatus.reviewed,
    ReviewDecision.needs_more_evidence: ClaimStatus.needs_more_evidence,
}


async def create_review(
    session: AsyncSession,
    claim: Claim,
    reviewer: User,
    *,
    decision: ReviewDecision,
    notes: str | None,
    overrides: dict | None,
) -> Review:
    if claim.status not in (ClaimStatus.ready_for_review, ClaimStatus.reviewed):
        raise ConflictError(
            f"Claim in status '{claim.status.value}' is not ready for review"
        )
    review = Review(
        tenant_id=claim.tenant_id, claim_id=claim.id, reviewer_id=reviewer.id,
        decision=decision, notes=notes, overrides=overrides,
    )
    session.add(review)
    claim.status = _DECISION_STATUS[decision]
    claim.reviewed_at = datetime.now(UTC)
    await session.flush()
    return review


async def list_reviews(session: AsyncSession, claim_id: uuid.UUID) -> list[Review]:
    rows = await session.scalars(
        select(Review).where(Review.claim_id == claim_id).order_by(Review.created_at.desc())
    )
    return list(rows)
