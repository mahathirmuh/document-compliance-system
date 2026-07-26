"""Centralized finding metadata, severity policy, and safe draft creation."""

from __future__ import annotations

import re

from app.schemas.compliance_internal import FindingDraft
from app.services.compliance._compat import (
    float_value,
    mapping,
    string_value,
)
from app.services.compliance.constants import (
    LANGUAGE_NAMES,
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG_RE = re.compile(r"<[^>\n]{1,500}>")
_WHITESPACE_RE = re.compile(r"[ \t]+")

_DEFINITIONS: dict[str, tuple[str, str, str, str]] = {
    FindingCode.INVALID_DOCUMENT_CODE: (
        FindingType.DOCUMENT_CODE,
        FindingSeverity.MAJOR,
        "Document code is invalid",
        "Align the document code with the selected validation rule.",
    ),
    FindingCode.MISSING_INDONESIAN: (
        FindingType.LANGUAGE_PRESENCE,
        FindingSeverity.MAJOR,
        "Required Indonesian content is missing",
        "Add sufficient Indonesian-language content and revalidate.",
    ),
    FindingCode.MISSING_ENGLISH: (
        FindingType.LANGUAGE_PRESENCE,
        FindingSeverity.MAJOR,
        "Required English content is missing",
        "Add sufficient English-language content and revalidate.",
    ),
    FindingCode.MISSING_CHINESE: (
        FindingType.LANGUAGE_PRESENCE,
        FindingSeverity.MAJOR,
        "Required Chinese content is missing",
        "Add sufficient Chinese-language content and revalidate.",
    ),
    FindingCode.LOW_INDONESIAN_COVERAGE: (
        FindingType.LANGUAGE_COVERAGE,
        FindingSeverity.MINOR,
        "Indonesian coverage is below the required threshold",
        "Increase eligible Indonesian-language coverage.",
    ),
    FindingCode.LOW_ENGLISH_COVERAGE: (
        FindingType.LANGUAGE_COVERAGE,
        FindingSeverity.MINOR,
        "English coverage is below the required threshold",
        "Increase eligible English-language coverage.",
    ),
    FindingCode.LOW_CHINESE_COVERAGE: (
        FindingType.LANGUAGE_COVERAGE,
        FindingSeverity.MINOR,
        "Chinese coverage is below the required threshold",
        "Increase eligible Chinese-language coverage.",
    ),
    FindingCode.MISSING_REQUIRED_SECTION: (
        FindingType.SECTION_MISSING,
        FindingSeverity.MAJOR,
        "A required section is missing",
        "Add the required canonical section using a recognized heading.",
    ),
    FindingCode.MISSING_SECTION_INDONESIAN: (
        FindingType.SECTION_LANGUAGE_MISSING,
        FindingSeverity.MAJOR,
        "Required section lacks Indonesian content",
        "Add Indonesian content to the identified section.",
    ),
    FindingCode.MISSING_SECTION_ENGLISH: (
        FindingType.SECTION_LANGUAGE_MISSING,
        FindingSeverity.MAJOR,
        "Required section lacks English content",
        "Add English content to the identified section.",
    ),
    FindingCode.MISSING_SECTION_CHINESE: (
        FindingType.SECTION_LANGUAGE_MISSING,
        FindingSeverity.MAJOR,
        "Required section lacks Chinese content",
        "Add Chinese content to the identified section.",
    ),
    FindingCode.SECTION_ORDER_INVALID: (
        FindingType.SECTION_ORDER,
        FindingSeverity.MINOR,
        "Section order does not match the configured order",
        "Reorder canonical sections or update the approved rule.",
    ),
    FindingCode.LANGUAGE_ORDER_INVALID: (
        FindingType.LANGUAGE_ORDER,
        FindingSeverity.MINOR,
        "Language order is invalid",
        "Use the configured language order within this structural group.",
    ),
    FindingCode.INCOMPLETE_TRANSLATION_GROUP: (
        FindingType.TRANSLATION_GROUP_INCOMPLETE,
        FindingSeverity.MINOR,
        "A structural translation group is incomplete",
        "Review the group and add each required language where applicable.",
    ),
    FindingCode.MISSING_TRANSLATION_GROUP_INDONESIAN: (
        FindingType.TRANSLATION_GROUP_INCOMPLETE,
        FindingSeverity.MINOR,
        "Translation group lacks Indonesian content",
        "Add Indonesian content to the structural group.",
    ),
    FindingCode.MISSING_TRANSLATION_GROUP_ENGLISH: (
        FindingType.TRANSLATION_GROUP_INCOMPLETE,
        FindingSeverity.MINOR,
        "Translation group lacks English content",
        "Add English content to the structural group.",
    ),
    FindingCode.MISSING_TRANSLATION_GROUP_CHINESE: (
        FindingType.TRANSLATION_GROUP_INCOMPLETE,
        FindingSeverity.MINOR,
        "Translation group lacks Chinese content",
        "Add Chinese content to the structural group.",
    ),
    FindingCode.TABLE_TRANSLATION_INCOMPLETE: (
        FindingType.TABLE_LANGUAGE_MISSING,
        FindingSeverity.MAJOR,
        "A multilingual table is incomplete",
        "Complete each required language row or column in the table.",
    ),
    FindingCode.TABLE_CELL_LANGUAGE_MISSING: (
        FindingType.CELL_LANGUAGE_MISSING,
        FindingSeverity.MINOR,
        "A required table-language cell is missing",
        "Populate the missing language cell where content is required.",
    ),
    FindingCode.XLSX_ROW_TRANSLATION_INCOMPLETE: (
        FindingType.TABLE_LANGUAGE_MISSING,
        FindingSeverity.MINOR,
        "An XLSX multilingual row is incomplete",
        "Complete the configured language cells in this worksheet row.",
    ),
    FindingCode.UNKNOWN_TEXT_EXCEEDS_THRESHOLD: (
        FindingType.UNKNOWN_LANGUAGE_EXCESS,
        FindingSeverity.MINOR,
        "Unknown-language text exceeds the threshold",
        "Review unclassified content and extraction quality.",
    ),
    FindingCode.MIXED_TEXT_EXCEEDS_THRESHOLD: (
        FindingType.MIXED_LANGUAGE_EXCESS,
        FindingSeverity.INFORMATION,
        "Mixed-language text exceeds the review threshold",
        "Review mixed blocks; mixed content is not automatically an error.",
    ),
    FindingCode.OCR_CONFIDENCE_TOO_LOW: (
        FindingType.OCR_CONFIDENCE,
        FindingSeverity.INFORMATION,
        "OCR confidence is too low for reliable validation",
        "Review OCR output before relying on the compliance result.",
    ),
    FindingCode.EXTRACTION_PARTIALLY_COMPLETED: (
        FindingType.EXTRACTION_QUALITY,
        FindingSeverity.INFORMATION,
        "Extraction completed only partially",
        "Review extraction warnings and retry when appropriate.",
    ),
    FindingCode.OCR_REQUIRED_NOT_COMPLETED: (
        FindingType.EXTRACTION_QUALITY,
        FindingSeverity.CRITICAL,
        "Required OCR has not completed",
        "Complete OCR and language detection before validating compliance.",
    ),
    FindingCode.MANUAL_FINDING: (
        FindingType.MANUAL,
        FindingSeverity.MINOR,
        "Manual compliance finding",
        "Review and address the manually recorded observation.",
    ),
}


def sanitize_user_text(value: str, *, maximum: int) -> str:
    text = _CONTROL_RE.sub("", value or "")
    text = _HTML_TAG_RE.sub("", text)
    text = "\n".join(
        _WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()
    ).strip()
    return text[:maximum]


class FindingFactory:
    """Create bounded, consistently classified finding drafts."""

    def create(
        self,
        finding_code: str,
        *,
        description: str | None = None,
        severity: str | None = None,
        title: str | None = None,
        recommendation: str | None = None,
        confidence: float | None = None,
        **location: object,
    ) -> FindingDraft:
        code = string_value(finding_code).upper()
        definition = _DEFINITIONS.get(
            code,
            (
                FindingType.STRUCTURE,
                FindingSeverity.INFORMATION,
                code.replace("_", " ").title(),
                "Review the compliance finding.",
            ),
        )
        finding_type, default_severity, default_title, default_recommendation = (
            definition
        )
        selected_severity = string_value(
            severity or default_severity,
        ).upper()
        if confidence is not None:
            selected_severity = self._confidence_adjusted_severity(
                selected_severity,
                confidence,
            )
        language = location.pop("language_code", None)
        metrics = mapping(location.pop("metrics", {}))
        if confidence is not None:
            metrics.setdefault("confidence", confidence)
        return FindingDraft(
            finding_code=code,
            finding_type=string_value(
                location.pop("finding_type", finding_type),
            ).upper(),
            severity=selected_severity,
            title=sanitize_user_text(
                title or default_title,
                maximum=500,
            ),
            description=sanitize_user_text(
                description
                or self._default_description(code, language),
                maximum=4000,
            ),
            recommendation=sanitize_user_text(
                recommendation or default_recommendation,
                maximum=2000,
            ),
            status=string_value(
                location.pop("status", FindingStatus.OPEN),
            ).upper(),
            container_id=location.pop("container_id", None),
            detected_section_id=location.pop("detected_section_id", None),
            detected_section_code=self._optional_string(
                location.pop(
                    "detected_section_code",
                    location.pop("section_code", None),
                ),
            ),
            translation_group_id=location.pop(
                "translation_group_id",
                None,
            ),
            translation_group_signature=self._optional_string(
                location.pop("translation_group_signature", None),
            ),
            extracted_block_id=location.pop("extracted_block_id", None),
            ocr_block_id=location.pop("ocr_block_id", None),
            page_number=self._optional_int(
                location.pop("page_number", None),
            ),
            worksheet_name=self._bounded_optional(
                location.pop("worksheet_name", None),
                500,
            ),
            cell_coordinate=self._bounded_optional(
                location.pop("cell_coordinate", None),
                100,
            ),
            source_reference=self._bounded_optional(
                location.pop("source_reference", None),
                1000,
            ),
            location=mapping(location.pop("location", {})),
            language_code=(
                string_value(language).casefold()
                if language is not None
                else None
            ),
            expected_value=mapping(
                location.pop("expected_value", {}),
            ),
            actual_value=mapping(location.pop("actual_value", {})),
            metrics=metrics,
            is_system_generated=bool(
                location.pop("is_system_generated", True),
            ),
        )

    def manual(
        self,
        *,
        severity: str,
        title: str,
        description: str,
        recommendation: str,
        **location: object,
    ) -> FindingDraft:
        return self.create(
            FindingCode.MANUAL_FINDING,
            severity=severity,
            title=title,
            description=description,
            recommendation=recommendation,
            is_system_generated=False,
            **location,
        )

    def with_severity(
        self,
        finding: FindingDraft,
        severity: str,
    ) -> FindingDraft:
        return finding.model_copy(update={"severity": severity.upper()})

    @staticmethod
    def _confidence_adjusted_severity(
        severity: str,
        confidence: float,
    ) -> str:
        bounded = max(0.0, min(1.0, float_value(confidence)))
        if bounded < 0.65:
            return FindingSeverity.INFORMATION
        if bounded < 0.80 and severity == FindingSeverity.CRITICAL:
            return FindingSeverity.MAJOR
        return severity

    @staticmethod
    def _default_description(code: str, language: object) -> str:
        language_name = LANGUAGE_NAMES.get(
            string_value(language).casefold(),
            string_value(language),
        )
        if language_name:
            return f"Required {language_name} evidence was not found."
        return code.replace("_", " ").capitalize() + "."

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _bounded_optional(value: object, maximum: int) -> str | None:
        if value is None:
            return None
        return sanitize_user_text(str(value), maximum=maximum)


def default_severity_for(finding_code: str) -> str:
    definition = _DEFINITIONS.get(str(finding_code).upper())
    return (
        string_value(definition[1])
        if definition
        else FindingSeverity.INFORMATION
    )


def finding_definition(
    finding_code: str,
) -> tuple[str, str, str, str] | None:
    return _DEFINITIONS.get(str(finding_code).upper())
