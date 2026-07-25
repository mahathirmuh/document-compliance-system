"""Department business rules and audited transactions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.department import Department
from app.models.user import User
from app.repositories.department_repository import DepartmentRepository
from app.schemas.department import (
    DepartmentCreate,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.schemas.master_data import MasterDataOption
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import (
    MasterDataServiceBase,
    audit_dump,
    business_error,
    conflict,
    not_found,
)


class DepartmentService(MasterDataServiceBase):
    entity_name = "Department"
    entity_type = "department"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = DepartmentRepository(session)

    @staticmethod
    def response(entity: Department) -> DepartmentResponse:
        return DepartmentResponse.model_validate(entity)

    async def list(
        self,
        *,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> DepartmentListResponse:
        items, total = await self.repository.list_page(
            search=search,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return DepartmentListResponse(
            items=[self.response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def get(self, entity_id: UUID) -> DepartmentResponse:
        entity = await self.repository.get_by_id(entity_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def options(self, *, active_only: bool = True) -> list[MasterDataOption]:
        entities = await self.repository.options(active_only=active_only)
        return [
            MasterDataOption.model_validate(entity) for entity in entities
        ]

    async def create(self, payload: DepartmentCreate) -> DepartmentResponse:
        existing = await self.repository.get_by_code(payload.code)
        if existing is not None:
            raise conflict(
                "Department code already exists.",
                field="code",
                title="Department could not be created.",
            )
        entity = Department(
            **payload.model_dump(by_alias=False),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.repository.add(entity)
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Department code already exists.",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_DEPARTMENT,
            entity_id=entity.id,
            description=f"Department {entity.code} was created.",
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message="Department code already exists.",
        )
        return response

    async def update(
        self,
        entity_id: UUID,
        payload: DepartmentUpdate,
    ) -> DepartmentResponse:
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
                "change department status.",
                field="isActive",
            )
        new_code = values.get("code")
        if new_code is not None and new_code != entity.code:
            duplicate = await self.repository.get_by_code(str(new_code))
            if duplicate is not None and duplicate.id != entity.id:
                raise conflict(
                    "Department code already exists.",
                    field="code",
                    title="Department could not be updated.",
                )
        for key, value in values.items():
            setattr(entity, key, value)
        entity.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Department code already exists.",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_DEPARTMENT,
            entity_id=entity.id,
            description=f"Department {entity.code} was updated.",
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Department code already exists.",
        )
        return response

    async def set_active(
        self,
        entity_id: UUID,
        *,
        active: bool,
    ) -> tuple[DepartmentResponse, int]:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        entity.is_active = active
        entity.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(entity, attribute_names=["updated_at"])
        response = self.response(entity)
        active_sections = (
            0
            if active
            else await self.repository.active_section_count(entity.id)
        )
        await self.commit_audited(
            action=(
                AuditAction.ACTIVATE_DEPARTMENT
                if active
                else AuditAction.DEACTIVATE_DEPARTMENT
            ),
            entity_id=entity.id,
            description=(
                f"Department {entity.code} was "
                f"{'activated' if active else 'deactivated'}."
                + (
                    f" {active_sections} active sections remain."
                    if active_sections
                    else ""
                )
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Department state could not be changed.",
            duplicate_field=None,
        )
        return response, active_sections
