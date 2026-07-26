"""Persistence operations for auditable compliance findings."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload, selectinload

from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.document import Document
from app.models.finding_occurrence import FindingOccurrence
from app.models.validation_finding import ValidationFinding


class ValidationFindingRepository:
    """Database-only finding reads, writes, and repeat lookup."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def base_statement(
        self,
        *,
        include_occurrences: bool = False,
        include_previous_finding: bool = False,
    ):
        return select(ValidationFinding).options(
            (
                selectinload(ValidationFinding.occurrences)
                if include_occurrences
                else raiseload(ValidationFinding.occurrences)
            ),
            (
                selectinload(ValidationFinding.previous_finding)
                if include_previous_finding
                else raiseload(ValidationFinding.previous_finding)
            ),
        )

    async def add(
        self,
        finding: ValidationFinding,
    ) -> ValidationFinding:
        self.session.add(finding)
        await self.session.flush()
        return finding

    async def add_many(
        self,
        findings: Sequence[ValidationFinding],
        *,
        batch_size: int = 1000,
    ) -> list[ValidationFinding]:
        items = list(findings)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def add_occurrences(
        self,
        occurrences: Sequence[FindingOccurrence],
        *,
        batch_size: int = 1000,
    ) -> list[FindingOccurrence]:
        items = list(occurrences)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def get_by_id(
        self,
        finding_id: UUID,
        *,
        for_update: bool = False,
        include_occurrences: bool = False,
        include_previous_finding: bool = False,
    ) -> ValidationFinding | None:
        statement = self.base_statement(
            include_occurrences=include_occurrences,
            include_previous_finding=include_previous_finding,
        ).where(
            ValidationFinding.id == finding_id
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def find_previous_match(
        self,
        *,
        document_revision_id: UUID,
        finding_code: FindingCode | str,
        source_reference: str | None,
        language_code: str | None,
        detected_section_id: UUID | None = None,
        exclude_run_id: UUID | None = None,
    ) -> ValidationFinding | None:
        code = finding_code.value if isinstance(finding_code, FindingCode) else finding_code
        statement = self.base_statement().where(
            ValidationFinding.document_revision_id == document_revision_id,
            ValidationFinding.finding_code == code,
            ValidationFinding.source_reference == source_reference,
            ValidationFinding.language_code == language_code,
            ValidationFinding.is_system_generated.is_(True),
        )
        if detected_section_id is not None:
            statement = statement.where(
                ValidationFinding.detected_section_id
                == detected_section_id
            )
        if exclude_run_id is not None:
            statement = statement.where(
                ValidationFinding.compliance_run_id != exclude_run_id
            )
        return (
            await self.session.execute(
                statement.order_by(
                    desc(ValidationFinding.created_at),
                    desc(ValidationFinding.id),
                ).limit(1)
            )
        ).scalar_one_or_none()

    async def list_for_run(
        self,
        compliance_run_id: UUID,
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> list[ValidationFinding]:
        result = await self.session.scalars(
            self.base_statement()
            .where(
                ValidationFinding.compliance_run_id == compliance_run_id
            )
            .order_by(
                self._severity_order(),
                desc(ValidationFinding.created_at),
                desc(ValidationFinding.id),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all())

    async def count_for_run(self, compliance_run_id: UUID) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(ValidationFinding.id)).where(
                        ValidationFinding.compliance_run_id
                        == compliance_run_id
                    )
                )
            )
            or 0
        )

    async def count_by_language_for_run(
        self,
        compliance_run_id: UUID,
    ) -> dict[str, int]:
        rows = await self.session.execute(
            select(
                ValidationFinding.language_code,
                func.count(ValidationFinding.id),
            )
            .where(
                ValidationFinding.compliance_run_id == compliance_run_id,
                ValidationFinding.language_code.is_not(None),
            )
            .group_by(ValidationFinding.language_code)
        )
        return {
            str(language): int(count)
            for language, count in rows.all()
            if language is not None
        }

    async def count_by_section_ids(
        self,
        section_ids: Sequence[UUID],
    ) -> dict[UUID, int]:
        ids = list(section_ids)
        if not ids:
            return {}
        rows = await self.session.execute(
            select(
                ValidationFinding.detected_section_id,
                func.count(ValidationFinding.id),
            )
            .where(ValidationFinding.detected_section_id.in_(ids))
            .group_by(ValidationFinding.detected_section_id)
        )
        return {
            section_id: int(count)
            for section_id, count in rows.all()
            if section_id is not None
        }

    async def count_by_translation_group_ids(
        self,
        group_ids: Sequence[UUID],
    ) -> dict[UUID, int]:
        ids = list(group_ids)
        if not ids:
            return {}
        rows = await self.session.execute(
            select(
                ValidationFinding.translation_group_id,
                func.count(ValidationFinding.id),
            )
            .where(ValidationFinding.translation_group_id.in_(ids))
            .group_by(ValidationFinding.translation_group_id)
        )
        return {
            group_id: int(count)
            for group_id, count in rows.all()
            if group_id is not None
        }

    @staticmethod
    def _severity_order():
        return case(
            (ValidationFinding.severity == FindingSeverity.CRITICAL, 1),
            (ValidationFinding.severity == FindingSeverity.MAJOR, 2),
            (ValidationFinding.severity == FindingSeverity.MINOR, 3),
            else_=4,
        )

    async def list_page(
        self,
        *,
        department_ids: Sequence[UUID] | None = None,
        search: str | None = None,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
        compliance_run_id: UUID | None = None,
        finding_code: FindingCode | None = None,
        finding_type: FindingType | None = None,
        severity: FindingSeverity | None = None,
        status: FindingStatus | None = None,
        language_code: str | None = None,
        assigned_to: UUID | None = None,
        created_by_system: bool | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ValidationFinding], int]:
        statement = self.base_statement().join(
            Document,
            Document.id == ValidationFinding.document_id,
        )
        if department_ids is not None:
            statement = statement.where(
                Document.department_id.in_(list(department_ids))
            )
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    ValidationFinding.title.ilike(pattern),
                    ValidationFinding.description.ilike(pattern),
                    ValidationFinding.source_reference.ilike(pattern),
                )
            )
        if document_id is not None:
            statement = statement.where(
                ValidationFinding.document_id == document_id
            )
        if revision_id is not None:
            statement = statement.where(
                ValidationFinding.document_revision_id == revision_id
            )
        if compliance_run_id is not None:
            statement = statement.where(
                ValidationFinding.compliance_run_id == compliance_run_id
            )
        if finding_code is not None:
            statement = statement.where(
                ValidationFinding.finding_code == finding_code
            )
        if finding_type is not None:
            statement = statement.where(
                ValidationFinding.finding_type == finding_type
            )
        if severity is not None:
            statement = statement.where(
                ValidationFinding.severity == severity
            )
        if status is not None:
            statement = statement.where(
                ValidationFinding.status == status
            )
        if language_code is not None:
            statement = statement.where(
                ValidationFinding.language_code == language_code
            )
        if assigned_to is not None:
            statement = statement.where(
                ValidationFinding.assigned_to == assigned_to
            )
        if created_by_system is not None:
            statement = statement.where(
                ValidationFinding.is_system_generated.is_(
                    created_by_system
                )
            )
        if created_from is not None:
            statement = statement.where(
                ValidationFinding.created_at >= created_from
            )
        if created_to is not None:
            statement = statement.where(
                ValidationFinding.created_at <= created_to
            )
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )
        result = await self.session.scalars(
            statement.order_by(
                self._severity_order(),
                desc(ValidationFinding.created_at),
                desc(ValidationFinding.id),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total
