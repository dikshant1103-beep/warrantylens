from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def record(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Append an immutable audit entry. Caller commits."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        before=before,
        after=after,
        ip=ip,
    )
    session.add(entry)
    return entry
