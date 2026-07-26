"""Recursive structured-log redaction for secrets and sensitive URLs."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "secret",
        "token",
        "client_secret",
        "access_token",
        "refresh_token",
        "certificate_password",
        "webhook_url",
        "telegram_bot_token",
        "delta_link",
        "database_url",
    }
)
_NORMALIZED_SENSITIVE_KEYS = frozenset(
    item.replace("-", "_") for item in SENSITIVE_KEYS
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(password|secret|client_secret|access_token|refresh_token|"
    r"certificate_password|telegram_bot_token)\s*[=:]\s*[^\s,;&]+"
)


def _sensitive_key(key: object) -> bool:
    normalized = str(key).strip().casefold().replace("-", "_")
    return normalized in _NORMALIZED_SENSITIVE_KEYS or any(
        marker in normalized for marker in ("password", "secret", "token")
    )


def redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc:
        return value
    query = [
        (key, REDACTED if _sensitive_key(key) else item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    try:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
    except ValueError:
        return value
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def redact_text(value: str) -> str:
    redacted = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", value)
    redacted = _KEY_VALUE_PATTERN.sub(
        lambda match: f"{match.group(1)}={REDACTED}",
        redacted,
    )
    for token in value.split():
        if "://" in token:
            redacted = redacted.replace(token, redact_url(token))
    return redacted


def redact_sensitive(value: Any, *, key: object | None = None) -> Any:
    if key is not None and _sensitive_key(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_sensitive(item, key=item_key)
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, set):
        return {redact_sensitive(item) for item in value}
    if isinstance(value, str):
        return redact_text(value)
    return value


class SensitiveDataFilter(logging.Filter):
    """Mutate a record copy's public message arguments before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive(record.msg)
        if isinstance(record.args, Mapping):
            record.args = redact_sensitive(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(redact_sensitive(item) for item in record.args)
        return True
