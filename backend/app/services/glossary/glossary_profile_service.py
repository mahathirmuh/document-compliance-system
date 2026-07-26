"""Scoped glossary profile management and resolution."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.glossary_profile import GlossaryProfile
from app.models.user import User
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_type_repository import DocumentTypeRepository
from app.repositories.glossary_profile_repository import (
    GlossaryProfileRepository,
)
from app.schemas.glossary import (
    GlossaryProfileCreate,
    GlossaryProfileListResponse,
    GlossaryProfileResponse,
    GlossaryProfileUpdate,
    GlossaryProfileValues,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.base import (
    GlossaryServiceBase,
    glossary_error,
    glossary_not_found,
)


class GlossaryProfileService(GlossaryServiceBase):
    """Create, update, archive, and resolve versioned profiles."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.profiles = GlossaryProfileRepository(session)
        self.departments = DepartmentRepository(session)
        self.document_types = DocumentTypeRepository(session)

    @staticmethod
    def response(profile: GlossaryProfile) -> GlossaryProfileResponse:
        return GlossaryProfileResponse(
            id=profile.id,
            code=profile.code,
            name=profile.name,
            description=profile.description,
            scope_type=profile.scope_type,
            department_id=profile.department_id,
            document_type_id=profile.document_type_id,
            is_default=profile.is_default,
            is_active=profile.is_active,
            version=profile.version,
            term_count=len(profile.terms),
            created_by=profile.created_by,
            updated_by=profile.updated_by,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    async def list(
        self,
        **filters: Any,
    ) -> GlossaryProfileListResponse:
        page = int(filters.pop("page", 1))
        page_size = int(filters.pop("page_size", 20))
        items, total = await self.profiles.list_page(
            department_ids=self.department_ids,
            page=page,
            page_size=page_size,
            **filters,
        )
        return GlossaryProfileListResponse(
            items=[self.response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=self.total_pages(total, page_size),
        )

    async def get(self, profile_id: UUID) -> GlossaryProfileResponse:
        profile = await self.profiles.get_by_id(
            profile_id,
            department_ids=self.department_ids,
        )
        if profile is None:
            raise glossary_not_found("Glossary profile")
        return self.response(profile)

    async def create(
        self,
        payload: GlossaryProfileCreate,
    ) -> GlossaryProfileResponse:
        await self._validate_values(payload)
        profile = GlossaryProfile(
            **payload.model_dump(by_alias=False),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        profile.terms = []
        await self.profiles.add(profile)
        response = self.response(profile)
        await self.audit(
            action=AuditAction.CREATE_GLOSSARY_PROFILE,
            entity_type="GlossaryProfile",
            entity_id=profile.id,
            description="Glossary profile created.",
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="Glossary profile code already exists.",
            field="code",
        )
        return response

    async def update(
        self,
        profile_id: UUID,
        payload: GlossaryProfileUpdate,
    ) -> GlossaryProfileResponse:
        profile = await self.profiles.get_by_id(
            profile_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if profile is None:
            raise glossary_not_found("Glossary profile")
        old = self.response(profile)
        values = self._merged_values(profile, payload)
        await self._validate_values(values, exclude_id=profile.id)
        for key, value in values.model_dump(by_alias=False).items():
            setattr(profile, key, value)
        profile.version += 1
        profile.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(
            profile,
            attribute_names=["updated_at"],
        )
        response = self.response(profile)
        await self.audit(
            action=AuditAction.UPDATE_GLOSSARY_PROFILE,
            entity_type="GlossaryProfile",
            entity_id=profile.id,
            description="Glossary profile updated.",
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="Glossary profile conflicts with existing data.",
            field="code",
        )
        return response

    async def archive(self, profile_id: UUID) -> GlossaryProfileResponse:
        return await self._set_active(profile_id, active=False)

    async def restore(self, profile_id: UUID) -> GlossaryProfileResponse:
        return await self._set_active(profile_id, active=True)

    async def resolve(
        self,
        *,
        department_id: UUID | None,
        document_type_id: UUID | None,
    ) -> list[GlossaryProfile]:
        return await self.profiles.resolve_for_scope(
            department_id=department_id,
            document_type_id=document_type_id,
        )

    async def _set_active(
        self,
        profile_id: UUID,
        *,
        active: bool,
    ) -> GlossaryProfileResponse:
        profile = await self.profiles.get_by_id(
            profile_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if profile is None:
            raise glossary_not_found("Glossary profile")
        old = self.response(profile)
        profile.is_active = active
        profile.version += 1
        profile.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(
            profile,
            attribute_names=["updated_at"],
        )
        response = self.response(profile)
        await self.audit(
            action=(
                AuditAction.UPDATE_GLOSSARY_PROFILE
                if active
                else AuditAction.ARCHIVE_GLOSSARY_PROFILE
            ),
            entity_type="GlossaryProfile",
            entity_id=profile.id,
            description=(
                "Glossary profile restored."
                if active
                else "Glossary profile archived."
            ),
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.session.commit()
        return response

    async def _validate_values(
        self,
        values: GlossaryProfileValues,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        if values.department_id is not None:
            department = await self.departments.get_by_id(
                values.department_id
            )
            if department is None:
                raise glossary_error(
                    "Department was not found.",
                    field="departmentId",
                )
        if values.document_type_id is not None:
            document_type = await self.document_types.get_by_id(
                values.document_type_id
            )
            if document_type is None:
                raise glossary_error(
                    "Document type was not found.",
                    field="documentTypeId",
                )
        if values.is_default and values.is_active:
            existing = await self.profiles.get_default_in_scope(
                scope_type=values.scope_type,
                department_id=values.department_id,
                document_type_id=values.document_type_id,
                exclude_id=exclude_id,
                for_update=True,
            )
            if existing is not None:
                raise glossary_error(
                    "An active default profile already exists in this scope.",
                    field="isDefault",
                    status_code=409,
                )

    @staticmethod
    def _merged_values(
        profile: GlossaryProfile,
        payload: GlossaryProfileUpdate,
    ) -> GlossaryProfileValues:
        current = {
            "code": profile.code,
            "name": profile.name,
            "description": profile.description,
            "scope_type": profile.scope_type,
            "department_id": profile.department_id,
            "document_type_id": profile.document_type_id,
            "is_default": profile.is_default,
            "is_active": profile.is_active,
        }
        current.update(
            payload.model_dump(by_alias=False, exclude_unset=True)
        )
        return GlossaryProfileValues.model_validate(current)
