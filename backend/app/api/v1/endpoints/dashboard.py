from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def overview(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await dashboard_service.overview(db, current.tenant_id)


@router.get("/risk-distribution")
async def risk_distribution(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await dashboard_service.risk_distribution(db, current.tenant_id)


@router.get("/completeness-stats")
async def completeness_stats(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await dashboard_service.completeness_stats(db, current.tenant_id)


@router.get("/reviewer-queue")
async def reviewer_queue(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await dashboard_service.reviewer_queue(db, current.tenant_id)
