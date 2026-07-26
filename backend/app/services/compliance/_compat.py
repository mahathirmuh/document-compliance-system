"""Small adapters that keep the pure engine DTO-implementation agnostic."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, is_dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


def read(value: object, name: str, default: T | None = None) -> object | T:
    """Read a snake-case field from a mapping, dataclass, or Pydantic object."""

    if isinstance(value, Mapping):
        if name in value:
            return value[name]
        camel_name = _camel(name)
        return value.get(camel_name, default)
    return getattr(value, name, default)


def first(
    value: object,
    *names: str,
    default: T | None = None,
) -> object | T:
    for name in names:
        candidate = read(value, name, None)
        if candidate is not None:
            return candidate
    return default


def enum_value(value: object, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def string_value(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def float_value(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return default


def int_value(value: object, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return default


def bool_value(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def sequence(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def string_list(value: object) -> list[str]:
    return [enum_value(item) for item in sequence(value)]


def mapping(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return {}


def option(rule: object, name: str, default: T) -> object | T:
    direct = read(rule, name, None)
    if direct is not None:
        return direct
    options = first(
        rule,
        "validation_options",
        "validation_options_json",
        "options",
        default={},
    )
    return read(mapping(options), name, default)


def copy_update(value: T, **updates: object) -> T:
    """Return a same-kind copy with updates without mutating caller data."""

    if isinstance(value, BaseModel):
        return value.model_copy(update=updates)  # type: ignore[return-value]
    if is_dataclass(value) and not isinstance(value, type):
        return replace(value, **updates)
    if isinstance(value, Mapping):
        return {**value, **updates}  # type: ignore[return-value]
    clone = object.__new__(type(value))
    if hasattr(value, "__dict__"):
        clone.__dict__.update(value.__dict__)
        clone.__dict__.update(updates)
        return clone
    raise TypeError(f"Cannot copy value of type {type(value).__name__}.")


def json_safe(value: object) -> object:
    """Convert engine values to JSON-safe primitives without source leakage."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return json_safe(value.model_dump(mode="python", by_alias=True))
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
            if not _sensitive_key(str(key))
        }
    if isinstance(value, Iterable) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [json_safe(item) for item in value]
    return str(value)


def object_id(value: object) -> str | None:
    identifier = first(value, "id", "block_id", default=None)
    return str(identifier) if identifier is not None else None


def language_code(value: object, default: str = "unknown") -> str:
    raw = first(
        value,
        "language_code",
        "primary_language_code",
        default=default,
    )
    return enum_value(raw, default).casefold()


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").casefold()
    return normalized in {
        "storage_path",
        "storagepath",
        "absolute_path",
        "absolutepath",
        "local_path",
        "localpath",
        "filesystem_path",
        "filesystempath",
        "stack_trace",
        "stacktrace",
        "traceback",
    }
