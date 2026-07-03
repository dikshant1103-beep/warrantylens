from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    catalog,
    claims,
    dashboard,
    health,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(claims.router, prefix="/claims", tags=["claims"])
api_router.include_router(dashboard.router)
