from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "warrantylens",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.orchestrator"],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="cpu",
    task_routes={
        # GPU stages (Sprint 3) will route to the "gpu" queue.
        "app.workers.orchestrator.run_pipeline": {"queue": "cpu"},
    },
)
