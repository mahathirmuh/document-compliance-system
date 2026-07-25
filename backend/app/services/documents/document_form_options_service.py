"""Scoped active master-data options required by document forms."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.department import Department
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.section import Section
from app.models.user import User
from app.models.validation_rule import ValidationRule
from app.schemas.document import (
    DocumentFormDepartmentOption,
    DocumentFormOptionsResponse,
    DocumentFormRuleOption,
    DocumentFormSectionOption,
    DocumentFormStatusOption,
    DocumentFormTypeOption,
)
from app.services.documents.base import DocumentAccessPolicy


class DocumentFormOptionsService:
    """Return only active options, with department scope enforced once."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
    ) -> None:
        self.session = session
        self.settings = settings
        self.policy = DocumentAccessPolicy(user)

    async def get(self) -> DocumentFormOptionsResponse:
        department_statement = select(Department).where(
            Department.deleted_at.is_(None),
            Department.is_active.is_(True),
        )
        section_statement = select(Section).where(
            Section.deleted_at.is_(None),
            Section.is_active.is_(True),
        )
        if not self.policy.view_all_departments:
            if self.policy.scope_department_id is None:
                department_statement = department_statement.where(
                    Department.id.is_(None)
                )
                section_statement = section_statement.where(
                    Section.id.is_(None)
                )
            else:
                department_statement = department_statement.where(
                    Department.id == self.policy.scope_department_id
                )
                section_statement = section_statement.where(
                    Section.department_id
                    == self.policy.scope_department_id
                )
        departments = list(
            (
                await self.session.scalars(
                    department_statement.order_by(Department.code)
                )
            ).all()
        )
        sections = list(
            (
                await self.session.scalars(
                    section_statement.order_by(
                        Section.department_id,
                        Section.code,
                    )
                )
            ).all()
        )
        document_types = list(
            (
                await self.session.scalars(
                    select(DocumentType)
                    .where(
                        DocumentType.deleted_at.is_(None),
                        DocumentType.is_active.is_(True),
                    )
                    .order_by(DocumentType.code)
                )
            ).all()
        )
        statuses = list(
            (
                await self.session.scalars(
                    select(DocumentStatus)
                    .where(
                        DocumentStatus.deleted_at.is_(None),
                        DocumentStatus.is_active.is_(True),
                    )
                    .order_by(
                        DocumentStatus.display_order,
                        DocumentStatus.code,
                    )
                )
            ).all()
        )
        rules = list(
            (
                await self.session.scalars(
                    select(ValidationRule)
                    .where(
                        ValidationRule.deleted_at.is_(None),
                        ValidationRule.is_active.is_(True),
                    )
                    .order_by(ValidationRule.code)
                )
            ).all()
        )
        active_rule_ids = {rule.id for rule in rules}
        return DocumentFormOptionsResponse(
            default_company_code=self.settings.default_company_code,
            departments=[
                DocumentFormDepartmentOption(
                    id=department.id,
                    code=department.code,
                    name=department.name,
                )
                for department in departments
            ],
            sections=[
                DocumentFormSectionOption(
                    id=section.id,
                    code=section.code,
                    name=section.name,
                    department_id=section.department_id,
                )
                for section in sections
            ],
            document_types=[
                DocumentFormTypeOption(
                    id=document_type.id,
                    code=document_type.code,
                    name=document_type.name,
                    requires_section=document_type.requires_section,
                    default_validation_rule_id=(
                        document_type.default_validation_rule_id
                        if document_type.default_validation_rule_id
                        in active_rule_ids
                        else None
                    ),
                )
                for document_type in document_types
            ],
            document_statuses=[
                DocumentFormStatusOption(
                    id=status.id,
                    code=status.code,
                    name=status.name,
                    is_initial=status.is_initial,
                )
                for status in statuses
            ],
            validation_rules=[
                DocumentFormRuleOption(
                    id=rule.id,
                    code=rule.code,
                    name=rule.name,
                    document_type_id=rule.document_type_id,
                    is_default=rule.is_default,
                )
                for rule in rules
            ],
        )
