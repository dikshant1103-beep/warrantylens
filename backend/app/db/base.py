from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


# Import models so Alembic's target_metadata sees them.
# (Imported at bottom to avoid circular imports.)
from app.db.models import (  # noqa: E402,F401
    ai,
    audit_log,
    claim,
    component,
    inspection_template,
    media,
    processing_job,
    refresh_token,
    scoring,
    tenant,
    user,
)
