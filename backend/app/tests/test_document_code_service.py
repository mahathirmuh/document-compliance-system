"""Unit tests for canonical Phase 4 document-code handling."""

import pytest

from app.services.documents.document_code_service import (
    DocumentCodeError,
    DocumentCodeService,
)


@pytest.fixture
def service() -> DocumentCodeService:
    return DocumentCodeService()


def test_generate_base_document_code_with_section_normalizes_case(
    service: DocumentCodeService,
) -> None:
    result = service.generate_base_document_code(
        company_code="  mti ",
        department_code=" hrm ",
        section_code=" ier ",
        document_type_code=" sop ",
        document_number=" 001-a ",
        requires_section=True,
    )

    assert result == "MTI-HRM-IER-SOP-001-A"


def test_generate_base_document_code_without_section(
    service: DocumentCodeService,
) -> None:
    result = service.generate_base_document_code(
        company_code="mti",
        department_code="hrm",
        section_code=None,
        document_type_code="pol",
        document_number="001",
        requires_section=False,
    )

    assert result == "MTI-HRM-POL-001"


def test_generate_base_document_code_accepts_hyphenated_document_type(
    service: DocumentCodeService,
) -> None:
    result = service.generate_base_document_code(
        company_code="MTI",
        department_code="HRM",
        section_code="IER",
        document_type_code="work-instruction",
        document_number="001",
        requires_section=True,
    )

    assert result == "MTI-HRM-IER-WORK-INSTRUCTION-001"
    with pytest.raises(DocumentCodeError):
        service.generate_base_document_code(
            company_code="MTI",
            department_code="HRM-OPS",
            section_code="IER",
            document_type_code="WORK-INSTRUCTION",
            document_number="001",
            requires_section=True,
        )


@pytest.mark.parametrize(
    ("section_code", "requires_section", "message"),
    [
        (None, True, "sectionCode is required"),
        ("IER", False, "sectionCode must be empty"),
    ],
)
def test_generate_base_document_code_enforces_section_requirement(
    service: DocumentCodeService,
    section_code: str | None,
    requires_section: bool,
    message: str,
) -> None:
    with pytest.raises(DocumentCodeError, match=message):
        service.generate_base_document_code(
            company_code="MTI",
            department_code="HRM",
            section_code=section_code,
            document_type_code="SOP",
            document_number="001",
            requires_section=requires_section,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("companyCode", ""),
        ("companyCode", "MTI-OPS"),
        ("departmentCode", "HR M"),
        ("sectionCode", "IER/OPS"),
        ("documentTypeCode", "SOP."),
    ],
)
def test_normalize_component_rejects_empty_or_unsafe_values(
    field: str,
    value: str,
) -> None:
    with pytest.raises(DocumentCodeError):
        DocumentCodeService.normalize_component(value, field=field)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2026/001",
        "001 A",
        "001@A",
    ],
)
def test_normalize_document_number_rejects_invalid_values(value: str) -> None:
    with pytest.raises(DocumentCodeError):
        DocumentCodeService.normalize_document_number(value)


def test_generate_full_document_code_normalizes_base_and_revision(
    service: DocumentCodeService,
) -> None:
    assert (
        service.generate_full_document_code(
            " mti-hrm-ier-sop-001 ",
            " rev1 ",
        )
        == "MTI-HRM-IER-SOP-001_Rev.001"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("000", "Rev.000"),
        ("001", "Rev.001"),
        ("Rev000", "Rev.000"),
        ("Rev.000", "Rev.000"),
        ("REV.000", "Rev.000"),
        ("rev.000", "Rev.000"),
        ("A", "Rev.A"),
        ("Rev.A", "Rev.A"),
        ("0", "Rev.000"),
        ("1", "Rev.001"),
        ("12", "Rev.012"),
        ("1234", "Rev.1234"),
        ("rev.b-2", "Rev.B-2"),
    ],
)
def test_normalize_revision_code_supports_all_required_forms(
    value: str,
    expected: str,
) -> None:
    assert DocumentCodeService.normalize_revision_code(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "Rev.",
        "1A",
        "Rev.1A",
        "_",
        "Rev.A_B",
        "Rev.A B",
        "Rev./A",
    ],
)
def test_normalize_revision_code_rejects_invalid_values(value: str) -> None:
    with pytest.raises(DocumentCodeError):
        DocumentCodeService.normalize_revision_code(value)


def test_revision_number_is_safe_for_large_numeric_revisions() -> None:
    assert DocumentCodeService.revision_number("2147483647") == 2_147_483_647
    assert DocumentCodeService.revision_number("2147483648") is None
    assert (
        DocumentCodeService.normalize_revision_code(
            "99999999999999999999999999"
        )
        == "Rev.99999999999999999999999999"
    )
    assert (
        DocumentCodeService.revision_number("99999999999999999999999999")
        is None
    )


def test_revision_code_rejects_values_over_the_storage_limit() -> None:
    with pytest.raises(DocumentCodeError, match="at most 26"):
        DocumentCodeService.normalize_revision_code("9" * 27)


@pytest.mark.parametrize("extension", ["pdf", "docx", "xlsx"])
def test_parse_document_filename_supports_required_extensions(
    service: DocumentCodeService,
    extension: str,
) -> None:
    parsed = service.parse_document_filename(
        f"MTI-HRM-IER-SOP-001_Rev.003.{extension}"
    )

    assert parsed.company_code == "MTI"
    assert parsed.department_code == "HRM"
    assert parsed.section_code == "IER"
    assert parsed.document_type_code == "SOP"
    assert parsed.document_number == "001"
    assert parsed.revision_code == "Rev.003"
    assert parsed.file_extension == extension
    assert parsed.base_document_code == "MTI-HRM-IER-SOP-001"
    assert parsed.full_document_code == "MTI-HRM-IER-SOP-001_Rev.003"


def test_parse_document_filename_extracts_multilingual_title_suffix(
    service: DocumentCodeService,
) -> None:
    title = (
        "Demin Plant - Reducing Reagent Mixing & Dosing "
        "脱盐水-还原剂药剂配制 (4706)"
    )
    parsed = service.parse_document_filename(
        f"MTI-ACP-APM-SOP-001_Rev. 000 - {title}.pdf",
        has_section=True,
    )

    assert parsed.company_code == "MTI"
    assert parsed.department_code == "ACP"
    assert parsed.section_code == "APM"
    assert parsed.document_type_code == "SOP"
    assert parsed.document_number == "001"
    assert parsed.revision_code == "Rev.000"
    assert parsed.document_title == title
    assert parsed.base_document_code == "MTI-ACP-APM-SOP-001"
    assert parsed.full_document_code == "MTI-ACP-APM-SOP-001_Rev.000"


def test_filename_title_can_contain_later_revision_markers(
    service: DocumentCodeService,
) -> None:
    parsed = service.parse_document_filename(
        (
            "MTI-HRM-IER-SOP-001_Rev.B-2 - "
            "Title _Rev.999 - attachment.docx.pdf"
        ),
        has_section=True,
    )

    assert parsed.document_number == "001"
    assert parsed.revision_code == "Rev.B-2"
    assert parsed.document_title == (
        "Title _Rev.999 - attachment.docx"
    )


@pytest.mark.parametrize(
    "filename",
    [
        "MTI-HRM-IER-SOP-001_Rev.000-Title.pdf",
        "MTI-HRM-IER-SOP-001_Rev.000 -Title.pdf",
        "MTI-HRM-IER-SOP-001_Rev.000- Title.pdf",
        "MTI-HRM-IER-SOP-001_Rev.1A - Title.pdf",
    ],
)
def test_filename_title_requires_an_unambiguous_separator_and_revision(
    service: DocumentCodeService,
    filename: str,
) -> None:
    with pytest.raises(DocumentCodeError):
        service.parse_document_filename(filename, has_section=True)


def test_filename_title_respects_document_title_limit(
    service: DocumentCodeService,
) -> None:
    with pytest.raises(DocumentCodeError, match="at most 500"):
        service.parse_document_filename(
            "MTI-HRM-IER-SOP-001_Rev.000 - "
            f"{'A' * 501}.pdf",
            has_section=True,
        )


def test_parse_document_code_accepts_bare_full_code(
    service: DocumentCodeService,
) -> None:
    parsed = service.parse_document_code(
        " mti-hrm-ier-sop-001_rev003 ",
        has_section=True,
    )

    assert parsed.base_document_code == "MTI-HRM-IER-SOP-001"
    assert parsed.revision_code == "Rev.003"
    assert parsed.full_document_code == "MTI-HRM-IER-SOP-001_Rev.003"
    assert parsed.file_extension is None


def test_parse_document_code_accepts_bare_alphabetic_revision(
    service: DocumentCodeService,
) -> None:
    parsed = service.parse_document_code(
        "MTI-HRM-POL-001_Rev.A",
        has_section=False,
    )

    assert parsed.revision_code == "Rev.A"
    assert parsed.file_extension is None


def test_parse_document_code_accepts_dotted_document_number(
    service: DocumentCodeService,
) -> None:
    parsed = service.parse_document_code(
        "MTI-HRM-POL-ABC.DEF",
        has_section=False,
    )

    assert parsed.document_number == "ABC.DEF"
    assert parsed.revision_code is None
    assert parsed.file_extension is None


def test_parse_candidates_include_hyphenated_document_type(
    service: DocumentCodeService,
) -> None:
    candidates = service.parse_document_code_candidates(
        "MTI-HRM-IER-WORK-INSTRUCTION-2026-001_Rev.A.pdf",
        has_section=True,
    )

    matched = [
        candidate
        for candidate in candidates
        if candidate.document_type_code == "WORK-INSTRUCTION"
    ]
    assert len(matched) == 1
    assert matched[0].document_number == "2026-001"
    assert matched[0].revision_code == "Rev.A"


def test_parse_no_section_with_hyphenated_number_uses_explicit_shape(
    service: DocumentCodeService,
) -> None:
    parsed = service.parse_document_filename(
        "MTI-HRM-POL-2026-001_Rev.003.pdf",
        has_section=False,
    )

    assert parsed.company_code == "MTI"
    assert parsed.department_code == "HRM"
    assert parsed.section_code is None
    assert parsed.document_type_code == "POL"
    assert parsed.document_number == "2026-001"
    assert parsed.base_document_code == "MTI-HRM-POL-2026-001"
    assert parsed.revision_code == "Rev.003"
    assert parsed.full_document_code == "MTI-HRM-POL-2026-001_Rev.003"


@pytest.mark.parametrize(
    "filename",
    [
        "MTI-HRM-IER-SOP-001_Rev.003.txt",
        "MTI-HRM-IER-SOP-001_Rev.003.xls",
        "MTI-HRM-IER-SOP-001_Rev.003.csv",
        "MTI-HRM-IER-SOP-001_Rev.003.exe",
        "MTI-HRM-IER-SOP-001_Rev.003",
    ],
)
def test_parse_document_filename_rejects_unsupported_or_missing_extension(
    service: DocumentCodeService,
    filename: str,
) -> None:
    with pytest.raises(DocumentCodeError):
        service.parse_document_filename(filename)


def test_parse_document_code_does_not_treat_unsupported_extension_as_revision(
    service: DocumentCodeService,
) -> None:
    with pytest.raises(DocumentCodeError, match='extension "txt" is not supported'):
        service.parse_document_code(
            "MTI-HRM-IER-SOP-001_Rev.003.txt",
            has_section=True,
        )


@pytest.mark.parametrize(
    "value",
    [
        "MTI-HRM-IER-SOP-001_Rev.1A.pdf",
        "MTI-HRM-IER-SOP-001_Rev.A_B.docx",
        "MTI-HRM-IER-SOP-001_Rev.A B.xlsx",
        "MTI-HRM-IER-SOP-001_Rev..pdf",
    ],
)
def test_parse_document_filename_rejects_invalid_revision(
    service: DocumentCodeService,
    value: str,
) -> None:
    with pytest.raises(DocumentCodeError):
        service.parse_document_filename(value, has_section=True)
