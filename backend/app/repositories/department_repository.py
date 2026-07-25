"""Department persistence operations."""

from typing import Any, ClassVar

from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute

from app.models.department import Department
from app.models.section import Section
from app.repositories.master_data_base import BaseMasterDataRepository


class DepartmentRepository(BaseMasterDataRepository[Department]):
    model = Department
    sortable_columns: ClassVar[
        dict[str, InstrumentedAttribute[Any]]
    ] = {
        "code": Department.code,
        "name": Department.name,
        "isActive": Department.is_active,
        "createdAt": Department.created_at,
        "updatedAt": Department.updated_at,
    }

    async def active_section_count(self, department_id: object) -> int:
        value = await self.session.scalar(
            select(func.count(Section.id)).where(
                Section.department_id == department_id,
                Section.is_active.is_(True),
                Section.deleted_at.is_(None),
            )
        )
        return int(value or 0)
