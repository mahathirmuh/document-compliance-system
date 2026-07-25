"""Database-backed master-data overview counts."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_status_repository import (
    DocumentStatusRepository,
)
from app.repositories.document_type_repository import DocumentTypeRepository
from app.repositories.section_repository import SectionRepository
from app.repositories.validation_rule_repository import ValidationRuleRepository
from app.schemas.master_data import MasterDataCount, MasterDataOverview


class MasterDataOverviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.departments = DepartmentRepository(session)
        self.sections = SectionRepository(session)
        self.document_types = DocumentTypeRepository(session)
        self.document_statuses = DocumentStatusRepository(session)
        self.validation_rules = ValidationRuleRepository(session)

    @staticmethod
    def _summary(values: tuple[int, int, int]) -> MasterDataCount:
        return MasterDataCount(
            total=values[0],
            active=values[1],
            inactive=values[2],
        )

    async def get(self) -> MasterDataOverview:
        return MasterDataOverview(
            departments=self._summary(await self.departments.counts()),
            sections=self._summary(await self.sections.counts()),
            document_types=self._summary(await self.document_types.counts()),
            document_statuses=self._summary(
                await self.document_statuses.counts()
            ),
            validation_rules=self._summary(
                await self.validation_rules.counts()
            ),
        )

