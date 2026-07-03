from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.metrics import render_latest
from app.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("startup", app=settings.app_name, env=settings.environment)

    if settings.is_production:
        problems = settings.assert_production_safe()
        if problems:
            # Fail fast rather than launch an insecure production service.
            raise RuntimeError(f"Unsafe production config: {'; '.join(problems)}")

    try:
        from app.services import storage_service

        storage_service.ensure_bucket()
    except Exception as exc:  # noqa: BLE001 — storage may be unavailable in some envs
        log.warning("bucket bootstrap skipped", error=str(exc))
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "AI EV Warranty Inspection Assistant — advisory only; humans make "
            "all final decisions. The system never claims fraud."
        ),
        lifespan=lifespan,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
    )

    # Order matters: outermost first. Security headers wrap everything; rate limit
    # before request handling; request-context for ids/metrics/logs.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        body, content_type = render_latest()
        return Response(content=body, media_type=content_type)

    return app


app = create_app()
