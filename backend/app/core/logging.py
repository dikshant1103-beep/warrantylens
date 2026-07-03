import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.debug
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
