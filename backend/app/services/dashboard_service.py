from __future__ import annotations

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.claim import Claim
from app.db.models.enums import ClaimStatus


async def overview(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    rows = await session.execute(
        select(Claim.status, func.count())
        .where(Claim.tenant_id == tenant_id)
        .group_by(Claim.status)
    )
    by_status = {s.value: 0 for s in ClaimStatus}
    total = 0
    for status, count in rows:
        by_status[status.value] = count
        total += count
    return {
        "total": total,
        "by_status": by_status,
        "pending_review": by_status.get(ClaimStatus.ready_for_review.value, 0),
        "processing": by_status.get(ClaimStatus.processing.value, 0)
        + by_status.get(ClaimStatus.queued.value, 0),
    }


async def risk_distribution(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    bucket = case(
        (Claim.risk_score < 33, "low"),
        (Claim.risk_score < 66, "elevated"),
        else_="high",
    )
    rows = await session.execute(
        select(bucket, func.count())
        .where(Claim.tenant_id == tenant_id, Claim.risk_score.is_not(None))
        .group_by(bucket)
    )
    dist = {"low": 0, "elevated": 0, "high": 0}
    for band, count in rows:
        dist[band] = count
    return dist


async def completeness_stats(session: AsyncSession, tenant_id: uuid.UUID) -> dict:
    row = await session.execute(
        select(
            func.avg(Claim.completeness_score),
            func.min(Claim.completeness_score),
            func.count(),
        ).where(Claim.tenant_id == tenant_id, Claim.completeness_score.is_not(None))
    )
    avg, low, n = row.one()
    return {
        "average": round(float(avg), 2) if avg is not None else None,
        "lowest": round(float(low), 2) if low is not None else None,
        "scored_claims": n,
    }


async def reviewer_queue(session: AsyncSession, tenant_id: uuid.UUID) -> list[dict]:
    rows = await session.scalars(
        select(Claim)
        .where(Claim.tenant_id == tenant_id, Claim.status == ClaimStatus.ready_for_review)
        .order_by(Claim.risk_score.desc().nullslast(), Claim.submitted_at.asc())
        .limit(50)
    )
    return [
        {
            "id": str(c.id),
            "claim_number": c.claim_number,
            "vin": c.vin,
            "risk_score": float(c.risk_score) if c.risk_score is not None else None,
            "completeness_score": float(c.completeness_score)
            if c.completeness_score is not None else None,
            "submitted_at": c.submitted_at.isoformat() if c.submitted_at else None,
        }
        for c in rows
    ]
