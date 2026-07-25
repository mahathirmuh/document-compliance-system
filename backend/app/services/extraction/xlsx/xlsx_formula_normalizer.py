"""JSON-safe XLSX values and non-executing formula metadata."""

import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from pydantic import JsonValue


def serialize_xlsx_value(value: object) -> JsonValue:
    """Convert an openpyxl cell value into a deterministic JSON value."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def display_xlsx_value(value: object) -> str:
    """Return a safe source-like string without formatting or calculation."""
    serialized = serialize_xlsx_value(value)
    if serialized is None:
        return ""
    if isinstance(serialized, bool):
        return "TRUE" if serialized else "FALSE"
    return str(serialized)


def formula_metadata(
    formula: object,
    cached_value: object,
) -> dict[str, JsonValue]:
    """Retain a formula and its existing cached value without evaluating it."""
    return {
        "formula": display_xlsx_value(formula),
        "cachedValue": serialize_xlsx_value(cached_value),
        "hasCachedValue": cached_value is not None,
        "formulaExecuted": False,
    }
