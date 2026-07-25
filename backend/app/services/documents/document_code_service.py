"""Canonical document-code generation and filename parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

COMPONENT_PATTERN = re.compile(r"^[A-Z0-9_]+$")
DOCUMENT_TYPE_COMPONENT_PATTERN = re.compile(r"^[A-Z0-9_-]+$")
DOCUMENT_NUMBER_PATTERN = re.compile(r"^[A-Z0-9._-]+$")
REVISION_VALUE_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]*$")
SUPPORTED_EXTENSIONS = frozenset({"pdf", "docx", "xlsx"})


class DocumentCodeError(ValueError):
    """A client-provided code cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class ParsedDocumentCode:
    """Syntactic pieces parsed before master-data resolution."""

    company_code: str
    department_code: str
    section_code: str | None
    document_type_code: str
    document_number: str
    revision_code: str | None
    file_extension: str | None
    base_document_code: str
    full_document_code: str | None


class DocumentCodeService:
    """Keep all code and revision formatting in one domain component."""

    @staticmethod
    def normalize_component(
        value: str,
        *,
        field: str,
        maximum: int = 20,
    ) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise DocumentCodeError(f"{field} is required.")
        if len(normalized) > maximum:
            raise DocumentCodeError(
                f"{field} must contain at most {maximum} characters."
            )
        if not COMPONENT_PATTERN.fullmatch(normalized):
            raise DocumentCodeError(
                f"{field} may contain only letters, numbers, and underscore."
            )
        return normalized

    @staticmethod
    def normalize_document_number(
        value: str,
        *,
        maximum: int = 50,
    ) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise DocumentCodeError("documentNumber is required.")
        if len(normalized) > maximum:
            raise DocumentCodeError(
                f"documentNumber must contain at most {maximum} characters."
            )
        if not DOCUMENT_NUMBER_PATTERN.fullmatch(normalized):
            raise DocumentCodeError(
                "documentNumber may contain only letters, numbers, dots, "
                "underscores, and hyphens."
            )
        return normalized

    @staticmethod
    def normalize_document_type_component(
        value: str,
        *,
        field: str = "documentTypeCode",
        maximum: int = 20,
    ) -> str:
        """Match the flexible Document Type code contract from Phase 3."""
        normalized = value.strip().upper()
        if not normalized:
            raise DocumentCodeError(f"{field} is required.")
        if len(normalized) > maximum:
            raise DocumentCodeError(
                f"{field} must contain at most {maximum} characters."
            )
        if not DOCUMENT_TYPE_COMPONENT_PATTERN.fullmatch(normalized):
            raise DocumentCodeError(
                f"{field} may contain only letters, numbers, underscores, "
                "and hyphens."
            )
        return normalized

    def validate_code_components(
        self,
        *,
        company_code: str,
        department_code: str,
        section_code: str | None,
        document_type_code: str,
        document_number: str,
        requires_section: bool,
    ) -> tuple[str, str, str | None, str, str]:
        company = self.normalize_component(
            company_code,
            field="companyCode",
        )
        department = self.normalize_component(
            department_code,
            field="departmentCode",
        )
        section = (
            self.normalize_component(section_code, field="sectionCode")
            if section_code is not None and section_code.strip()
            else None
        )
        document_type = self.normalize_document_type_component(
            document_type_code,
            field="documentTypeCode",
        )
        number = self.normalize_document_number(document_number)
        if requires_section and section is None:
            raise DocumentCodeError(
                "sectionCode is required for this document type."
            )
        if not requires_section and section is not None:
            raise DocumentCodeError(
                "sectionCode must be empty for this document type."
            )
        return company, department, section, document_type, number

    def generate_base_document_code(
        self,
        *,
        company_code: str,
        department_code: str,
        section_code: str | None,
        document_type_code: str,
        document_number: str,
        requires_section: bool,
    ) -> str:
        company, department, section, document_type, number = (
            self.validate_code_components(
                company_code=company_code,
                department_code=department_code,
                section_code=section_code,
                document_type_code=document_type_code,
                document_number=document_number,
                requires_section=requires_section,
            )
        )
        components = [company, department]
        if section is not None:
            components.append(section)
        components.extend((document_type, number))
        return "-".join(components)

    def generate_full_document_code(
        self,
        base_document_code: str,
        revision_code: str,
    ) -> str:
        base = base_document_code.strip().upper()
        if not base:
            raise DocumentCodeError("baseDocumentCode is required.")
        return f"{base}_{self.normalize_revision_code(revision_code)}"

    @staticmethod
    def normalize_revision_code(value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise DocumentCodeError("revisionCode is required.")
        match = re.fullmatch(r"(?:REV\.?)?(.+)", normalized)
        assert match is not None
        revision_value = match.group(1).strip()
        if not revision_value or len(revision_value) > 26:
            raise DocumentCodeError(
                "revisionCode must contain a value of at most 26 characters."
            )
        if revision_value.isdigit():
            revision_value = revision_value.zfill(3)
        elif not REVISION_VALUE_PATTERN.fullmatch(revision_value):
            raise DocumentCodeError(
                "revisionCode must be numeric or start with a letter and "
                "contain only letters, numbers, dots, and hyphens."
            )
        result = f"Rev.{revision_value}"
        if len(result) > 30:
            raise DocumentCodeError(
                "revisionCode must contain at most 30 characters."
            )
        return result

    @classmethod
    def revision_number(cls, value: str) -> int | None:
        normalized = cls.normalize_revision_code(value)[4:]
        if not normalized.isdigit():
            return None
        number = int(normalized)
        return number if number <= 2_147_483_647 else None

    def parse_document_filename(
        self,
        value: str,
        *,
        has_section: bool | None = None,
    ) -> ParsedDocumentCode:
        candidate = PurePath(value.strip()).name
        suffix = PurePath(candidate).suffix.lower()
        if not suffix:
            raise DocumentCodeError(
                "Filename must use a supported .pdf, .docx, or .xlsx extension."
            )
        extension = suffix.removeprefix(".")
        if extension not in SUPPORTED_EXTENSIONS:
            raise DocumentCodeError(
                f'File extension "{extension}" is not supported.'
            )
        return self._parse(
            candidate[: -len(suffix)],
            file_extension=extension,
            has_section=has_section,
        )

    def parse_document_code(
        self,
        value: str,
        *,
        has_section: bool | None = None,
    ) -> ParsedDocumentCode:
        candidate = value.strip()
        suffix = PurePath(candidate).suffix.lower()
        if suffix.removeprefix(".") in SUPPORTED_EXTENSIONS:
            return self.parse_document_filename(
                candidate,
                has_section=has_section,
            )
        if (
            suffix
            and suffix.removeprefix(".").isalpha()
            and "_rev" in candidate.lower()
            and not candidate[: -len(suffix)].upper().endswith("_REV")
        ):
            raise DocumentCodeError(
                f'File extension "{suffix.removeprefix(".")}" is not '
                "supported."
            )
        return self._parse(
            candidate,
            file_extension=None,
            has_section=has_section,
        )

    def parse_document_code_candidates(
        self,
        value: str,
        *,
        has_section: bool,
    ) -> list[ParsedDocumentCode]:
        """Enumerate type/number boundaries for master-aware resolution."""
        candidate = value.strip()
        suffix = PurePath(candidate).suffix.lower()
        extension: str | None = None
        if suffix.removeprefix(".") in SUPPORTED_EXTENSIONS:
            candidate = PurePath(candidate).name[: -len(suffix)]
            extension = suffix.removeprefix(".")
        elif (
            suffix
            and suffix.removeprefix(".").isalpha()
            and "_rev" in candidate.lower()
            and not candidate[: -len(suffix)].upper().endswith("_REV")
        ):
            raise DocumentCodeError(
                f'File extension "{suffix.removeprefix(".")}" is not '
                "supported."
            )

        normalized = candidate.strip().upper()
        revision_match = re.fullmatch(r"(.+)_(REV(?:\.)?.+)", normalized)
        base_code = (
            revision_match.group(1)
            if revision_match is not None
            else normalized
        )
        parts = base_code.split("-")
        type_index = 3 if has_section else 2
        type_segment_count = len(parts) - type_index - 1
        if type_segment_count < 1:
            raise DocumentCodeError("Document code is missing a component.")

        candidates: list[ParsedDocumentCode] = []
        errors: list[DocumentCodeError] = []
        for segments in range(1, type_segment_count + 1):
            try:
                parsed = self._parse(
                    candidate,
                    file_extension=extension,
                    has_section=has_section,
                    document_type_segments=segments,
                )
            except DocumentCodeError as exc:
                errors.append(exc)
                continue
            if parsed not in candidates:
                candidates.append(parsed)
        if candidates:
            return candidates
        if errors:
            raise errors[-1]
        raise DocumentCodeError("Document code is invalid.")

    def _parse(
        self,
        candidate: str,
        *,
        file_extension: str | None,
        has_section: bool | None,
        document_type_segments: int = 1,
    ) -> ParsedDocumentCode:
        normalized = candidate.strip().upper()
        revision_code: str | None = None
        base_code = normalized
        # Full document codes always use the explicit Rev prefix. Capture the
        # complete suffix first so invalid underscores cannot be reinterpreted
        # as part of the base code by regex backtracking.
        revision_match = re.fullmatch(r"(.+)_(REV(?:\.)?.+)", normalized)
        if revision_match is not None:
            base_code = revision_match.group(1)
            try:
                revision_code = self.normalize_revision_code(
                    revision_match.group(2)
                )
            except DocumentCodeError as exc:
                raise DocumentCodeError(
                    "revisionCode in the document code is invalid."
                ) from exc
        parts = base_code.split("-")
        if len(parts) < 4:
            raise DocumentCodeError(
                "Document code must include company, department, document "
                "type, and document number."
            )
        if has_section is None:
            has_section = len(parts) >= 5
        type_index = 3 if has_section else 2
        minimum = type_index + document_type_segments + 1
        if len(parts) < minimum:
            raise DocumentCodeError("Document code is missing a component.")
        company = self.normalize_component(parts[0], field="companyCode")
        department = self.normalize_component(
            parts[1],
            field="departmentCode",
        )
        if has_section:
            section = self.normalize_component(
                parts[2],
                field="sectionCode",
            )
            document_type = self.normalize_document_type_component(
                "-".join(
                    parts[
                        type_index : type_index + document_type_segments
                    ]
                ),
                field="documentTypeCode",
            )
        else:
            section = None
            document_type = self.normalize_document_type_component(
                "-".join(
                    parts[
                        type_index : type_index + document_type_segments
                    ]
                ),
                field="documentTypeCode",
            )
        number_parts = parts[type_index + document_type_segments :]
        number = self.normalize_document_number("-".join(number_parts))
        generated_base = self.generate_base_document_code(
            company_code=company,
            department_code=department,
            section_code=section,
            document_type_code=document_type,
            document_number=number,
            requires_section=has_section,
        )
        full_code = (
            self.generate_full_document_code(
                generated_base,
                revision_code,
            )
            if revision_code is not None
            else None
        )
        return ParsedDocumentCode(
            company_code=company,
            department_code=department,
            section_code=section,
            document_type_code=document_type,
            document_number=number,
            revision_code=revision_code,
            file_extension=file_extension,
            base_document_code=generated_base,
            full_document_code=full_code,
        )
