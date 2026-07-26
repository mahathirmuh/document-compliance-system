"""Operational tests for the explicit Phase 9 model installer."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.download_similarity_model import (
    DEFAULT_MODEL,
    configured_target,
    default_model_root,
)


def test_host_default_model_root_stays_inside_repository(
    tmp_path: Path,
) -> None:
    script_path = (
        tmp_path
        / "document-compliance-system"
        / "backend"
        / "scripts"
        / "download_similarity_model.py"
    )

    assert default_model_root(script_path) == (
        tmp_path
        / "document-compliance-system"
        / "models"
        / "similarity"
    )


def test_configured_target_honours_explicit_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured_root = tmp_path / "private-models"
    monkeypatch.setenv("SIMILARITY_MODEL_PATH", str(configured_root))
    monkeypatch.delenv("SIMILARITY_MODEL_NAME", raising=False)

    model_name, target = configured_target()

    assert model_name == DEFAULT_MODEL
    assert target == (
        configured_root
        / "sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
    )


def test_configured_target_rejects_empty_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMILARITY_MODEL_PATH", "   ")

    with pytest.raises(
        ValueError,
        match="SIMILARITY_MODEL_PATH cannot be empty",
    ):
        configured_target()
