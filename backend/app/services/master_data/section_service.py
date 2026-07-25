"""Section business rules and audited transactions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.section import Section
from app.models.user import User
from app.repositories.department_repository import DepartmentRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.master_data import MasterDataOption
from app.schemas.section import (
    SectionCreate,
    SectionListResponse,
    SectionResponse,
    SectionUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import (
    MasterDataServiceBase,
    audit_dump,
    business_error,
    conflict,
    not_found,
)


class SectionService(MasterDataServiceBase):
    entity_name = "Section"
    entity_type = "section"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = SectionRepository(session)
        self.departments = DepartmentRepository(session)

    @staticmethod
    def response(entity: Section) -> SectionResponse:
        department = (
            MasterDataOption.model_validate(entity.department)
            if entity.department is not None
            else None
        )
        return SectionResponse(
            id=entity.id,
            department_id=entity.department_id,
            department=department,
            code=entity.code,
            name=entity.name,
            description=entity.description,
            is_active=entity.is_active,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list(
        self,
        *,
        department_id: UUID | None,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> SectionListResponse:
        items, total = await self.repository.list_page(
            department_id=department_id,
            search=search,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return SectionListResponse(
            items=[self.response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def get(self, entity_id: UUID) -> SectionResponse:
        entity = await self.repository.get_by_id(entity_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def options(
        self,
        *,
        department_id: UUID | None,
        active_only: bool,
    ) -> list[MasterDataOption]:
        entities = await self.repository.options(
            department_id=department_id,
            active_only=active_only,
        )
        return [
            MasterDataOption.model_validate(entity) for entity in entities
        ]

    async def _active_department(self, department_id: UUID) -> object:
        department = await self.departments.get_by_id(department_id)
        if department is None:
            raise business_error(
                "Department was not found.",
                field="departmentId",
            )
        if not department.is_active:
            raise business_error(
                "Department must be active.",
                field="departmentId",
            )
        return department

    async def create(self, payload: SectionCreate) -> SectionResponse:
        await self._active_department(payload.department_id)
        duplicate = await self.repository.get_by_department_and_code(
            payload.department_id,
            payload.code,
        )
        if duplicate is not None:
            raise conflict(
                "Section code already exists in this department.",
                field="code",
                title="Section could not be created.",
            )
        entity = Section(
            **payload.model_dump(by_alias=False),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.repository.add(entity)
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Section code already exists in this department.",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_SECTION,
            entity_id=entity.id,
            description=f"Section {entity.code} was created.",
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message=(
                "Section code already exists in this department."
            ),
        )
        return response

    async def update(
        self,
        entity_id: UUID,
        payload: SectionUpdate,
    ) -> SectionResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        values = payload.model_dump(exclude_unset=True, by_alias=False)
        if (
            "is_active" in values
            and values["is_active"] != entity.is_active
        ):
            raise business_error(
                "Use the dedicated activate or deactivate endpoint to "
                "change section status.",
                field="isActive",
            )
        next_department_id = values.get(
            "department_id",
            entity.department_id,
        )
        if next_department_id != entity.department_id:
            await self._active_department(next_department_id)
        next_code = str(values.get("code", entity.code))
        duplicate = await self.repository.get_by_department_and_code(
            next_department_id,
            next_code,
        )
        if duplicate is not None and duplicate.id != entity.id:
            raise conflict(
                "Section code already exists in this department.",
                field="code",
                title="Section could not be updated.",
            )
        for key, value in values.items():
            setattr(entity, key, value)
        entity.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Section code already exists in this department.",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_SECTION,
            entity_id=entity.id,
            description=f"Section {entity.code} was updated.",
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message=(
                "Section code already exists in this department."
            ),
        )
        return response

    async def set_active(
        self,
        entity_id: UUID,
        *,
        active: bool,
    ) -> SectionResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        if active:
            await self._active_department(entity.department_id)
        old = audit_dump(self.response(entity))
        entity.is_active = active
        entity.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(entity, attribute_names=["updated_at"])
        response = self.response(entity)
        await self.commit_audited(
            action=(
                AuditAction.ACTIVATE_SECTION
                if active
                else AuditAction.DEACTIVATE_SECTION
            ),
            entity_id=entity.id,
            description=(
                f"Section {entity.code} was "
                f"{'activated' if active else 'deactivated'}."
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Section state could not be changed.",
            duplicate_field=None,
        )
        return response
