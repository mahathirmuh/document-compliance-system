"""Verify private-storage objects against a JSON Lines hash manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


def _safe_path(root: Path, key: str) -> Path:
    relative = PurePosixPath(key)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"Unsafe storage key: {key!r}")
    candidate = root.joinpath(*relative.parts).resolve()
    candidate.relative_to(root)
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root: Path, manifest: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    checked = missing = mismatched = 0
    with manifest.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            entry = json.loads(line)
            key = str(entry["storageKey"])
            expected = str(entry["sha256"]).lower()
            path = _safe_path(resolved_root, key)
            checked += 1
            if not path.is_file():
                missing += 1
                continue
            if _sha256(path) != expected:
                mismatched += 1
    return {
        "checked": checked,
        "missing": missing,
        "mismatched": mismatched,
        "valid": missing == 0 and mismatched == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    summary = verify(arguments.storage_root, arguments.manifest)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
