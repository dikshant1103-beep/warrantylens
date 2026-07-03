from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
