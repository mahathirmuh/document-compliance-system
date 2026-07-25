"""Document-status business rules and audited transactions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.document_status import DocumentStatus
from app.models.user import User
from app.repositories.document_status_repository import (
    DocumentStatusRepository,
)
from app.schemas.document_status import (
    DocumentStatusCreate,
    DocumentStatusListResponse,
    DocumentStatusResponse,
    DocumentStatusUpdate,
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


class DocumentStatusService(MasterDataServiceBase):
    entity_name = "Document Status"
    entity_type = "document_status"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = DocumentStatusRepository(session)

    @staticmethod
    def response(entity: DocumentStatus) -> DocumentStatusResponse:
        return DocumentStatusResponse.model_validate(entity)

    async def _ensure_initial_available(
        self,
        *,
        requested: bool,
        exclude_id: UUID | None = None,
    ) -> None:
        if not requested:
            return
        initial = await self.repository.get_initial(
            exclude_id=exclude_id,
            for_update=True,
        )
        if initial is not None:
            raise conflict(
                "Only one document status may be initial.",
                field="isInitial",
                title="Document Status could not be saved.",
            )

    async def list(
        self,
        *,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> DocumentStatusListResponse:
        items, total = await self.repository.list_page(
            search=search,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return DocumentStatusListResponse(
            items=[self.response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def get(self, entity_id: UUID) -> DocumentStatusResponse:
        entity = await self.repository.get_by_id(entity_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def options(self, *, active_only: bool = True) -> list[MasterDataOption]:
        entities = await self.repository.options(active_only=active_only)
        return [
            MasterDataOption.model_validate(entity) for entity in entities
        ]

    async def create(
        self,
        payload: DocumentStatusCreate,
    ) -> DocumentStatusResponse:
        if await self.repository.get_by_code(payload.code) is not None:
            raise conflict(
                "Document status code already exists.",
                field="code",
                title="Document Status could not be created.",
            )
        await self._ensure_initial_available(requested=payload.is_initial)
        entity = DocumentStatus(
            **payload.model_dump(by_alias=False),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.repository.add(entity)
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message=(
                    "Document status code already exists or another "
                    "initial status is configured."
                ),
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_DOCUMENT_STATUS,
            entity_id=entity.id,
            description=f"Document status {entity.code} was created.",
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message=(
                "Document status code already exists or another initial "
                "status is configured."
            ),
        )
        return response

    async def update(
        self,
        entity_id: UUID,
        payload: DocumentStatusUpdate,
    ) -> DocumentStatusResponse:
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
                "change document status state.",
                field="isActive",
            )
        new_code = values.get("code")
        if new_code is not None and new_code != entity.code:
            duplicate = await self.repository.get_by_code(str(new_code))
            if duplicate is not None and duplicate.id != entity.id:
                raise conflict(
                    "Document status code already exists.",
                    field="code",
                    title="Document Status could not be updated.",
                )
        await self._ensure_initial_available(
            requested=bool(values.get("is_initial", entity.is_initial)),
            exclude_id=entity.id,
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
                message=(
                    "Document status code already exists or another "
                    "initial status is configured."
                ),
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_DOCUMENT_STATUS,
            entity_id=entity.id,
            description=f"Document status {entity.code} was updated.",
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message=(
                "Document status code already exists or another initial "
                "status is configured."
            ),
        )
        return response

    async def set_active(
        self,
        entity_id: UUID,
        *,
        active: bool,
    ) -> DocumentStatusResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        entity.is_active = active
        entity.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(entity, attribute_names=["updated_at"])
        response = self.response(entity)
        await self.commit_audited(
            action=(
                AuditAction.ACTIVATE_DOCUMENT_STATUS
                if active
                else AuditAction.DEACTIVATE_DOCUMENT_STATUS
            ),
            entity_id=entity.id,
            description=(
                f"Document status {entity.code} was "
                f"{'activated' if active else 'deactivated'}."
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Document status state could not be changed.",
            duplicate_field=None,
        )
        return response
