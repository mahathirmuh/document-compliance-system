"""Synthetic Phase 8 fixture generation and extraction regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.extraction import ExtractionResultStatus
from app.services.extraction.extractor_factory import get_extractor
from scripts.generate_phase8_sample_documents import generate

EXPECTED_FIXTURES = {
    "complete-three-language.docx",
    "incomplete-table.docx",
    "languages-as-rows.xlsx",
    "low-confidence-grouping.pdf",
    "missing-chinese.docx",
    "missing-language-cell.xlsx",
    "missing-purpose-section.docx",
    "three-language-columns.xlsx",
    "three-language-pdf.pdf",
    "wrong-language-order.docx",
    "wrong-order-pdf.pdf",
}


def _texts(result: object) -> list[str]:
    document = result.model_dump()
    return [
        str(block["text"])
        for container in document["containers"]
        for block in container["blocks"]
        if block.get("text")
    ]


def test_phase8_fixture_generator_outputs_exact_inventory(
    tmp_path: Path,
) -> None:
    outputs = generate(tmp_path)

    assert {output.name for output in outputs} == EXPECTED_FIXTURES
    assert all(output.is_file() and output.stat().st_size > 0 for output in outputs)


@pytest.mark.asyncio
async def test_phase8_fixtures_use_existing_read_only_extractors(
    tmp_path: Path,
) -> None:
    outputs = generate(tmp_path)

    for output in outputs:
        result = await get_extractor(output.suffix).extract(output, {})
        assert result.status is ExtractionResultStatus.COMPLETED, output.name
        assert result.containers, output.name
        assert _texts(result), output.name


@pytest.mark.asyncio
async def test_phase8_fixture_variants_preserve_expected_evidence(
    tmp_path: Path,
) -> None:
    outputs = {output.name: output for output in generate(tmp_path)}

    complete = await get_extractor("docx").extract(
        outputs["complete-three-language.docx"],
        {},
    )
    missing_chinese = await get_extractor("docx").extract(
        outputs["missing-chinese.docx"],
        {},
    )
    columns = await get_extractor("xlsx").extract(
        outputs["three-language-columns.xlsx"],
        {},
    )
    rows = await get_extractor("xlsx").extract(
        outputs["languages-as-rows.xlsx"],
        {},
    )

    assert any("\u672c\u7a0b\u5e8f" in text for text in _texts(complete))
    assert not any("\u672c\u7a0b\u5e8f" in text for text in _texts(missing_chinese))
    assert any("Bahasa Indonesia" in text for text in _texts(columns))
    assert any("Language" in text for text in _texts(rows))
