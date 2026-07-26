"""Required-language completeness per page, DOCX part, or worksheet."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import TypedDict

from app.schemas.compliance_internal import (
    ComplianceBlockData,
    ComplianceValidationContext,
    ValidatorResult,
)
from app.services.compliance._compat import (
    bool_value,
    enum_value,
    first,
    int_value,
    read,
    string_list,
    string_value,
)
from app.services.compliance.constants import (
    LANGUAGE_NAMES,
    MISSING_LANGUAGE_CODES,
    FindingSeverity,
)
from app.services.compliance.findings.finding_factory import FindingFactory
from app.services.compliance.validators._helpers import (
    block_characters,
    eligible_block,
    required_languages,
    result,
    skipped_result,
    validator_enabled,
)
from app.services.compliance.validators.base_validator import (
    BaseComplianceValidator,
)


class _ContainerLocation(TypedDict):
    container_id: object
    page_number: int | None
    worksheet_name: str | None
    source_reference: str
    location: dict[str, object]


class ContainerCompletenessValidator(BaseComplianceValidator):
    code = "CONTAINER_COMPLETENESS"
    name = "Container completeness"
    weight = 0.0

    def __init__(self, finding_factory: FindingFactory | None = None) -> None:
        self.findings = finding_factory or FindingFactory()

    async def validate(
        self,
        context: ComplianceValidationContext,
    ) -> ValidatorResult:
        if not validator_enabled(context, self.code):
            return skipped_result(context, self.code, scoring=False)
        options = context.rule.validation_options
        require_all = bool_value(
            first(
                options,
                "require_all_languages_per_container",
                "requireAllLanguagesPerContainer",
                default=True,
            ),
            True,
        )
        if not require_all:
            return result(
                self.code,
                maximum_score=0,
                score=0,
                status="SKIPPED",
                metrics={"enabled": True, "requireAllLanguages": False},
            )
        configured_types = string_list(
            first(
                options,
                "container_types",
                "containerTypes",
                default=(
                    "PDF_PAGE",
                    "DOCX_BODY",
                    "DOCX_HEADER",
                    "DOCX_FOOTER",
                    "XLSX_WORKSHEET",
                ),
            ),
        )
        selected_types = {item.upper() for item in configured_types}
        minimum_characters = int_value(
            first(
                options,
                "ignore_containers_below_character_count",
                "ignoreContainersBelowCharacterCount",
                default=20,
            ),
            20,
        )
        languages = required_languages(context)
        blocks_by_container: dict[
            object | None,
            list[ComplianceBlockData],
        ] = defaultdict(list)
        for block in context.blocks:
            blocks_by_container[block.container_id].append(block)
        evaluated = 0
        complete = 0
        generated = []
        details: list[dict[str, object]] = []
        for container in context.containers:
            container_type = container.container_type.upper()
            if container_type not in selected_types:
                continue
            blocks = list(container.blocks) or blocks_by_container.get(
                container.id,
                [],
            )
            character_count = (
                container.character_count
                or sum(block_characters(block) for block in blocks)
            )
            if character_count < minimum_characters:
                continue
            evaluated += 1
            present = {
                block.language_code.casefold()
                for block in blocks
                if eligible_block(block)
            }
            missing = [
                language for language in languages if language not in present
            ]
            if not missing:
                complete += 1
            container_location = self._location(container, blocks)
            for language in missing:
                generated.append(
                    self.findings.create(
                        MISSING_LANGUAGE_CODES.get(
                            language,
                            f"MISSING_{language.upper()}",
                        ),
                        severity=FindingSeverity.MINOR,
                        language_code=language,
                        description=(
                            f"{LANGUAGE_NAMES.get(language, language)} is "
                            f"missing from {container_type}."
                        ),
                        expected_value={
                            "requiredLanguages": list(languages),
                        },
                        actual_value={
                            "detectedLanguages": sorted(present),
                            "missingLanguages": missing,
                        },
                        **container_location,
                    ),
                )
            details.append(
                {
                    "containerId": str(container.id) if container.id else None,
                    "containerType": container_type,
                    "containerIndex": container.container_index,
                    "characterCount": character_count,
                    "detectedLanguages": tuple(sorted(present)),
                    "missingLanguages": tuple(missing),
                },
            )
        return result(
            self.code,
            maximum_score=0,
            score=0,
            findings=generated,
            evaluated=bool(evaluated),
            status=(
                "PASSED"
                if evaluated and complete == evaluated
                else ("PARTIAL" if evaluated else "NOT_EVALUATED")
            ),
            metrics={
                "evaluatedContainers": evaluated,
                "completeContainers": complete,
                "containers": details,
            },
        )

    @staticmethod
    def _location(
        container: object,
        blocks: Sequence[object],
    ) -> _ContainerLocation:
        container_type = enum_value(
            read(container, "container_type", ""),
        ).upper()
        index = int_value(read(container, "container_index", 0))
        name = string_value(read(container, "container_name", ""))
        first_block = blocks[0] if blocks else None
        source_reference = (
            string_value(read(first_block, "source_reference", ""))
            if first_block is not None
            else f"{container_type}:index={index}"
        )
        return {
            "container_id": read(container, "id", None),
            "page_number": (
                index if container_type == "PDF_PAGE" and index >= 1 else None
            ),
            "worksheet_name": (
                name if container_type == "XLSX_WORKSHEET" else None
            ),
            "source_reference": source_reference,
            "location": {
                "containerType": container_type,
                "containerIndex": index,
            },
        }
