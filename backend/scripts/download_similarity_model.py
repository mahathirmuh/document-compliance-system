"""Explicitly install or verify the configured local similarity model.

This script is never imported by application startup. It may access the
network only when an operator invokes it without ``--offline-verify``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


def default_model_root(script_path: Path | None = None) -> Path:
    """Resolve a safe persistent default for container and host execution."""

    resolved_script = (script_path or Path(__file__)).resolve()
    backend_root = resolved_script.parents[1]
    filesystem_root = Path(backend_root.anchor)
    if backend_root.name == "app" and backend_root.parent == filesystem_root:
        return backend_root / "models" / "similarity"
    return backend_root.parent / "models" / "similarity"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a sentence-transformer into private local storage."
    )
    parser.add_argument(
        "--offline-verify",
        action="store_true",
        help="Verify local files only; never contact the network.",
    )
    return parser.parse_args()


def configured_target() -> tuple[str, Path]:
    model_name = os.getenv("SIMILARITY_MODEL_NAME", DEFAULT_MODEL).strip()
    configured_root = os.getenv("SIMILARITY_MODEL_PATH")
    if configured_root is None:
        root = default_model_root()
    elif configured_root.strip():
        root = Path(configured_root.strip()).expanduser()
    else:
        raise ValueError("SIMILARITY_MODEL_PATH cannot be empty.")
    if not model_name:
        raise ValueError("SIMILARITY_MODEL_NAME cannot be empty.")
    if "\x00" in str(root):
        raise ValueError("SIMILARITY_MODEL_PATH is invalid.")
    return model_name, root / model_name.replace("/", "--")


def is_installed(target: Path) -> bool:
    return target.is_dir() and (
        (target / "config.json").is_file()
        or (target / "modules.json").is_file()
    )


def verify(model_name: str, target: Path) -> int:
    if not is_installed(target):
        print(
            f"Similarity model is not installed at {target}.",
            file=sys.stderr,
        )
        return 2
    metadata = read_metadata(target)
    installed_name = metadata.get("modelName")
    if installed_name and installed_name != model_name:
        print(
            "Installed model metadata does not match "
            "SIMILARITY_MODEL_NAME.",
            file=sys.stderr,
        )
        return 3
    print(f"Similarity model is available offline at {target}.")
    if metadata:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


def install(model_name: str, target: Path) -> int:
    if is_installed(target):
        print(f"Similarity model already exists at {target}.")
        return verify(model_name, target)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "sentence-transformers is not installed. Install the approved "
            "backend ML dependencies before running this script.",
            file=sys.stderr,
        )
        return 4
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {model_name} to {target} ...")
    try:
        model = SentenceTransformer(model_name)
        model.save(str(target))
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            "Similarity model download failed: "
            f"{type(exc).__name__}. Existing document data was not touched.",
            file=sys.stderr,
        )
        return 5
    metadata = {
        "modelName": model_name,
        "provider": "sentence_transformer",
        "installedAt": datetime.now(UTC).isoformat(),
        "localOnlyAtRuntime": True,
    }
    (target / "model-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Similarity model installation completed.")
    return verify(model_name, target)


def read_metadata(target: Path) -> dict[str, object]:
    path = target / "model-metadata.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    args = parse_args()
    try:
        model_name, target = configured_target()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.offline_verify:
        return verify(model_name, target)
    return install(model_name, target)


if __name__ == "__main__":
    raise SystemExit(main())
