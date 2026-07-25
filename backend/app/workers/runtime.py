"""One persistent asyncio loop per Celery worker child process."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery.signals import worker_process_shutdown

from app.database.session import dispose_engine

ResultT = TypeVar("ResultT")
_event_loop: asyncio.AbstractEventLoop | None = None


def run_async(coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Run async database work on the same loop for every task in a child."""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
    return _event_loop.run_until_complete(coroutine)


@worker_process_shutdown.connect
def close_worker_runtime(**_: object) -> None:
    """Dispose loop-bound database connections before closing the loop."""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = None
        return
    try:
        _event_loop.run_until_complete(dispose_engine())
        _event_loop.run_until_complete(_event_loop.shutdown_asyncgens())
    finally:
        _event_loop.close()
        _event_loop = None
