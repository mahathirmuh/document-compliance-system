"""Install official PaddleOCR inference models into the private model volume.

The application never calls this module during startup or recognition. Network
access is isolated to this explicit operator command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
DEFAULT_MODEL_ROOT = Path("models/ocr")
MODEL_BASE_URL = (
    "https://paddle-model-ecology.bj.bcebos.com/"
    "paddlex/official_inference_model/paddle3.0.0"
)


@dataclass(frozen=True, slots=True)
class ModelArchive:
    """One official archive and the local profile directories it populates."""

    name: str
    url: str
    checksum_environment: str
    targets: tuple[PurePosixPath, ...]


MODEL_ARCHIVES = (
    ModelArchive(
        name="PP-OCRv5_mobile_det",
        url=f"{MODEL_BASE_URL}/PP-OCRv5_mobile_det_infer.tar",
        checksum_environment="OCR_MODEL_SHA256_PP_OCRV5_MOBILE_DET",
        targets=(
            PurePosixPath("latin/detection"),
            PurePosixPath("chinese_simplified/detection"),
        ),
    ),
    ModelArchive(
        name="latin_PP-OCRv5_mobile_rec",
        url=(
            f"{MODEL_BASE_URL}/"
            "latin_PP-OCRv5_mobile_rec_infer.tar"
        ),
        checksum_environment="OCR_MODEL_SHA256_LATIN_PP_OCRV5_MOBILE_REC",
        targets=(PurePosixPath("latin/recognition"),),
    ),
    ModelArchive(
        name="PP-OCRv5_mobile_rec",
        url=f"{MODEL_BASE_URL}/PP-OCRv5_mobile_rec_infer.tar",
        checksum_environment="OCR_MODEL_SHA256_PP_OCRV5_MOBILE_REC",
        targets=(PurePosixPath("chinese_simplified/recognition"),),
    ),
    ModelArchive(
        name="PP-LCNet_x1_0_doc_ori",
        url=f"{MODEL_BASE_URL}/PP-LCNet_x1_0_doc_ori_infer.tar",
        checksum_environment="OCR_MODEL_SHA256_PP_LCNET_DOC_ORI",
        targets=(PurePosixPath("orientation"),),
    ),
)


def normalized_checksum(value: str | None) -> str | None:
    """Validate an optional SHA-256 supplied by deployment configuration."""
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError("OCR model checksums must be 64 hexadecimal characters.")
    return normalized


def model_directory_ready(path: Path) -> bool:
    """Require at least one actual model file, not merely a placeholder."""
    return path.is_dir() and any(
        child.is_file() and child.name != ".gitkeep"
        for child in path.rglob("*")
    )


def _download_archive(
    *,
    source_url: str,
    destination: Path,
    expected_sha256: str | None,
) -> str:
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError("OCR model sources must be absolute HTTPS URLs.")

    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "document-compliance-model-setup/0.8.0"},
        method="GET",
    )
    digest = hashlib.sha256()
    downloaded = 0
    with urllib.request.urlopen(request, timeout=60) as response:
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) > MAX_ARCHIVE_BYTES:
            raise ValueError("OCR model archive exceeds the safety limit.")
        with destination.open("xb") as output:
            while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
                downloaded += len(chunk)
                if downloaded > MAX_ARCHIVE_BYTES:
                    raise ValueError("OCR model archive exceeds the safety limit.")
                digest.update(chunk)
                output.write(chunk)
                print(
                    f"\rDownloaded {downloaded / (1024 * 1024):.1f} MiB",
                    end="",
                    flush=True,
                )
    print()
    if downloaded == 0:
        raise ValueError("Downloaded OCR model archive is empty.")
    actual_sha256 = digest.hexdigest()
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError("OCR model checksum verification failed.")
    return actual_sha256


def _safe_extract(archive_path: Path, output_directory: Path) -> Path:
    """Extract regular files/directories only and reject path traversal."""
    output_directory = output_directory.resolve()
    with tarfile.open(archive_path, mode="r:*") as archive:
        members = archive.getmembers()
        if not members:
            raise ValueError("OCR model archive contains no files.")
        for member in members:
            member_path = PurePosixPath(member.name)
            if (
                member_path.is_absolute()
                or ".." in member_path.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("OCR model archive contains an unsafe entry.")
            resolved = (output_directory / Path(*member_path.parts)).resolve()
            if output_directory not in resolved.parents and resolved != output_directory:
                raise ValueError("OCR model archive escapes its destination.")
            archive.extract(member, output_directory, filter="data")

    children = [
        child
        for child in output_directory.iterdir()
        if child.name != "__MACOSX"
    ]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return output_directory


def install_models(model_root: Path) -> None:
    """Download missing official archives and populate all profile directories."""
    model_root = model_root.expanduser().resolve()
    model_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase7-ocr-models-") as temporary:
        temporary_root = Path(temporary)
        for specification in MODEL_ARCHIVES:
            targets = [
                model_root.joinpath(*target.parts)
                for target in specification.targets
            ]
            if all(model_directory_ready(target) for target in targets):
                print(f"{specification.name}: already installed")
                continue

            archive_path = temporary_root / f"{specification.name}.tar"
            expected_sha256 = normalized_checksum(
                os.environ.get(specification.checksum_environment)
            )
            try:
                actual_sha256 = _download_archive(
                    source_url=specification.url,
                    destination=archive_path,
                    expected_sha256=expected_sha256,
                )
                extracted = _safe_extract(
                    archive_path,
                    temporary_root / f"{specification.name}-extracted",
                )
                if not model_directory_ready(extracted):
                    raise ValueError(
                        f"{specification.name} archive has no model files."
                    )
                for target in targets:
                    if model_directory_ready(target):
                        continue
                    if target.exists():
                        raise ValueError(
                            f"Incomplete model directory must be removed: {target}"
                        )
                    shutil.copytree(extracted, target)
                    manifest = {
                        "model": specification.name,
                        "source": specification.url,
                        "sha256": actual_sha256,
                    }
                    (target / ".model-manifest.json").write_text(
                        json.dumps(manifest, indent=2),
                        encoding="utf-8",
                    )
                    print(f"{specification.name}: installed in {target}")
            finally:
                archive_path.unlink(missing_ok=True)


def main() -> int:
    """Run explicit model setup without leaking paths through the API."""
    parser = argparse.ArgumentParser(
        description="Download official PaddleOCR models for Phase 7.",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path(
            os.environ.get("OCR_MODEL_ROOT", str(DEFAULT_MODEL_ROOT))
        ),
    )
    arguments = parser.parse_args()
    try:
        install_models(arguments.model_root)
    except (OSError, tarfile.TarError, urllib.error.URLError, ValueError) as exc:
        print(f"OCR model setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
