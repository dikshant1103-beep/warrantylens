"""Helpers to run async DB code inside synchronous Celery tasks."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion in a fresh event loop (per task call).

    Each Celery task gets its own event loop. The async engine's connection
    pool must NOT be shared across loops (asyncpg connections are bound to the
    loop that created them), so we dispose the engine pool at the end of every
    task — the next task then opens fresh connections in its own loop.
    """

    async def _wrapped() -> T:
        from app.db.session import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())
