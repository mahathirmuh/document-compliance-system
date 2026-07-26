"""Export a redacted operational configuration snapshot."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

SENSITIVE = re.compile(
    r"(password|secret|token|authorization|cookie|certificate|webhook|"
    r"connection_string|database_url|redis_url)",
    re.IGNORECASE,
)
ALLOWED_PREFIXES = (
    "APP_",
    "API_",
    "DB_",
    "REDIS_",
    "CELERY_",
    "MICROSOFT_",
    "SHAREPOINT_",
    "NOTIFICATION_",
    "RATE_LIMIT_",
    "MALWARE_",
    "OTEL_",
    "METRICS_",
    "TRUSTED_",
    "CORS_",
)


def export_configuration() -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in sorted(os.environ.items()):
        if not key.startswith(ALLOWED_PREFIXES):
            continue
        result[key] = "[REDACTED]" if SENSITIVE.search(key) else value
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(export_configuration(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Redacted configuration written to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
