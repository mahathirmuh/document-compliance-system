"""Compact JSON production logs enriched with correlation IDs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.log_redaction import redact_sensitive, redact_text
from app.core.request_id import current_request_id

_HANDLER_MARKER = "_document_compliance_json_handler"


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "requestId": getattr(record, "request_id", None) or current_request_id(),
        }
        for field in (
            "event",
            "http_method",
            "http_route",
            "http_status",
            "duration_ms",
            "task_name",
            "task_id",
        ):
            if hasattr(record, field):
                payload[field] = redact_sensitive(getattr(record, field))
        if record.exc_info and record.exc_info[0] is not None:
            payload["exceptionType"] = record.exc_info[0].__name__
        return json.dumps(
            redact_sensitive(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


def configure_application_logging(
    *,
    level: str,
    json_enabled: bool,
) -> None:
    """Configure one process-wide handler without duplicating test/app factories."""

    resolved_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(resolved_level)
    if not json_enabled:
        return

    for handler in root.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            handler.setLevel(resolved_level)
            return

    handler = logging.StreamHandler()
    handler.setLevel(resolved_level)
    handler.setFormatter(JsonLogFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    root.handlers.clear()
    root.addHandler(handler)
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
