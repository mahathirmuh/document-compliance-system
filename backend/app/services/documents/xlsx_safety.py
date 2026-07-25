"""Shared sanitization for strings written to XLSX workbooks."""

import re
from typing import Any

XML_ILLEGAL_CHARACTERS = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
)


def excel_safe(value: Any) -> Any:
    """Remove XML-illegal controls and neutralize spreadsheet formulas."""
    if not isinstance(value, str):
        return value
    sanitized = XML_ILLEGAL_CHARACTERS.sub("", value)
    if sanitized.startswith(("=", "+", "-", "@")):
        return f"'{sanitized}"
    return sanitized
