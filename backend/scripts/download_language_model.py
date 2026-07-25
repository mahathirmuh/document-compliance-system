"""Download the official fastText language-identification model on demand.

This setup command is intentionally not called during application startup.
Production workers only read the local model configured by
``LANGUAGE_MODEL_PATH``.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_MODEL_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/"
    "supervised-models/lid.176.bin"
)
DEFAULT_MODEL_PATH = Path("models/language/lid.176.bin")
MAX_MODEL_BYTES = 256 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for a local model file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_existing(path: Path, expected_sha256: str | None) -> bool:
    """Return whether an existing non-empty file passes configured checks."""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if expected_sha256 is None:
        return True
    return sha256_file(path) == expected_sha256


def download_model(
    *,
    destination: Path,
    source_url: str,
    expected_sha256: str | None,
) -> Path:
    """Download to a private temporary file, verify, then atomically replace."""
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError("LANGUAGE_MODEL_URL must be an absolute HTTPS URL.")

    normalized_sha256 = (
        expected_sha256.strip().lower() if expected_sha256 else None
    )
    if normalized_sha256 is not None and (
        len(normalized_sha256) != 64
        or any(character not in "0123456789abcdef" for character in normalized_sha256)
    ):
        raise ValueError("LANGUAGE_MODEL_SHA256 must be 64 hexadecimal characters.")

    destination = destination.expanduser().resolve()
    if validate_existing(destination, normalized_sha256):
        print(f"Language model already valid: {destination}")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    temporary.unlink(missing_ok=True)

    digest = hashlib.sha256()
    downloaded = 0
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "document-compliance-model-setup/0.7.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > MAX_MODEL_BYTES:
                raise ValueError("Language model response exceeds the safety limit.")
            with temporary.open("xb") as output:
                while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
                    downloaded += len(chunk)
                    if downloaded > MAX_MODEL_BYTES:
                        raise ValueError(
                            "Language model download exceeds the safety limit."
                        )
                    digest.update(chunk)
                    output.write(chunk)
                    print(
                        f"\rDownloaded {downloaded / (1024 * 1024):.1f} MiB",
                        end="",
                        flush=True,
                    )
    except (OSError, urllib.error.URLError, ValueError):
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if downloaded:
            print()

    if downloaded == 0:
        temporary.unlink(missing_ok=True)
        raise ValueError("Downloaded language model is empty.")
    actual_sha256 = digest.hexdigest()
    if normalized_sha256 is not None and actual_sha256 != normalized_sha256:
        temporary.unlink(missing_ok=True)
        raise ValueError("Language model checksum verification failed.")

    os.replace(temporary, destination)
    print(f"Language model ready: {destination}")
    print(f"SHA256: {actual_sha256}")
    return destination


def main() -> int:
    """Parse environment-aware CLI arguments and perform one controlled setup."""
    parser = argparse.ArgumentParser(
        description="Download the official fastText lid.176.bin model.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(
            os.environ.get("LANGUAGE_MODEL_PATH", str(DEFAULT_MODEL_PATH))
        ),
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("LANGUAGE_MODEL_URL", DEFAULT_MODEL_URL),
    )
    parser.add_argument(
        "--sha256",
        default=os.environ.get("LANGUAGE_MODEL_SHA256") or None,
    )
    arguments = parser.parse_args()
    try:
        download_model(
            destination=arguments.path,
            source_url=arguments.url,
            expected_sha256=arguments.sha256,
        )
    except (OSError, urllib.error.URLError, ValueError) as exc:
        print(f"Language model setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
