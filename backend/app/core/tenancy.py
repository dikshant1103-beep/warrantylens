"""Tenant context.

The current tenant id is stored in a ContextVar set per-request (from the JWT)
so the service/repository layer can scope queries without threading tenant_id
through every signature. Defense-in-depth: endpoints still pass tenant_id
explicitly to services in Sprint 1; this context is the shared source of truth.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar(
    "current_tenant_id", default=None
)


def set_current_tenant(tenant_id: uuid.UUID | None) -> None:
    _current_tenant_id.set(tenant_id)


def get_current_tenant() -> uuid.UUID | None:
    return _current_tenant_id.get()
