"""Propagate bounded request correlation IDs through Celery messages."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from celery.signals import before_task_publish, task_postrun, task_prerun

from app.core.request_id import (
    current_request_id,
    normalize_request_id,
    request_id_context,
)

_HEADER_NAME = "request_id"
_task_context_tokens: dict[str, Any] = {}


@before_task_publish.connect(weak=False)
def add_request_id_to_task_headers(
    headers: dict[str, Any] | None = None,
    **_: object,
) -> None:
    """Attach the current HTTP/job correlation ID to the outgoing task."""

    if headers is None:
        return
    existing = headers.get(_HEADER_NAME)
    headers[_HEADER_NAME] = normalize_request_id(
        str(existing) if existing is not None else current_request_id()
    )


@task_prerun.connect(weak=False)
def activate_task_request_id(
    task_id: str | None = None,
    task: Any = None,
    **_: object,
) -> None:
    """Activate the propagated ID while the worker executes the task."""

    identifier = str(task_id or uuid4())
    request_headers = getattr(getattr(task, "request", None), "headers", None)
    propagated = (
        request_headers.get(_HEADER_NAME)
        if isinstance(request_headers, dict)
        else None
    )
    _task_context_tokens[identifier] = request_id_context.set(
        normalize_request_id(
            str(propagated) if propagated is not None else identifier
        )
    )


@task_postrun.connect(weak=False)
def clear_task_request_id(
    task_id: str | None = None,
    **_: object,
) -> None:
    """Restore the worker context after every success or failure."""

    if task_id is None:
        return
    token = _task_context_tokens.pop(str(task_id), None)
    if token is not None:
        request_id_context.reset(token)

