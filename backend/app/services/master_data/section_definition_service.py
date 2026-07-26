"""Audited CRUD services for section-alias profiles and definitions."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import (
    AuditAction,
    Permission,
    has_permission,
)
from app.core.exceptions import ApplicationError
from app.models.section_alias_profile import SectionAliasProfile
from app.models.section_definition import SectionDefinition
from app.models.user import User
from app.repositories.section_alias_profile_repository import (
    SectionAliasProfileRepository,
)
from app.repositories.section_definition_repository import (
    SectionDefinitionRepository,
)
from app.schemas.common import ErrorDetail
from app.schemas.section_detection import (
    SectionAliasProfileCreate,
    SectionAliasProfileListResponse,
    SectionAliasProfileResponse,
    SectionAliasProfileUpdate,
    SectionDefinitionCreate,
    SectionDefinitionListResponse,
    SectionDefinitionResponse,
    SectionDefinitionUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import (
    MasterDataServiceBase,
    audit_dump,
    business_error,
    conflict,
    not_found,
)


def _ensure_can_configure(user: User) -> None:
    if has_permission(
        user.role,
        Permission.COMPLIANCE_CONFIGURE_RULES,
        is_superuser=user.is_superuser,
    ):
        return
    raise ApplicationError(
        "Permission denied.",
        status_code=HTTPStatus.FORBIDDEN,
        errors=[
            ErrorDetail(
                field=None,
                message=(
                    "compliance:configure_rules permission is required."
                ),
            )
        ],
    )


class SectionAliasProfileService(MasterDataServiceBase):
    """Profile CRUD with a single-default invariant."""

    entity_name = "Section Alias Profile"
    entity_type = "section_alias_profile"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = SectionAliasProfileRepository(session)

    @staticmethod
    def response(
        entity: SectionAliasProfile,
    ) -> SectionAliasProfileResponse:
        definitions = list(entity.definitions)
        return SectionAliasProfileResponse(
            id=entity.id,
            code=entity.code,
            name=entity.name,
            description=entity.description,
            is_default=entity.is_default,
            is_active=entity.is_active,
            definition_count=len(definitions),
            alias_count=sum(
                len(definition.aliases) for definition in definitions
            ),
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
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
    ) -> SectionAliasProfileListResponse:
        items, total = await self.repository.list_page(
            search=search,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return SectionAliasProfileListResponse(
            items=[self.response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def get(self, profile_id: UUID) -> SectionAliasProfileResponse:
        entity = await self.repository.get_by_id(profile_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def create(
        self,
        payload: SectionAliasProfileCreate,
    ) -> SectionAliasProfileResponse:
        _ensure_can_configure(self.user)
        if await self.repository.get_by_code(payload.code) is not None:
            raise conflict(
                "Section alias profile code already exists.",
                field="code",
            )
        if payload.is_default:
            existing_default = await self.repository.get_default(
                for_update=True
            )
            if existing_default is not None:
                existing_default.is_default = False
                existing_default.updated_by = self.user.id
                await self.session.flush()
        entity = SectionAliasProfile(
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
                message=(
                    "Section alias profile code or default already exists."
                ),
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_SECTION_DEFINITION,
            entity_id=entity.id,
            description=f"Section alias profile {entity.code} was created.",
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message=(
                "Section alias profile code or default already exists."
            ),
        )
        return response

    async def update(
        self,
        profile_id: UUID,
        payload: SectionAliasProfileUpdate,
    ) -> SectionAliasProfileResponse:
        _ensure_can_configure(self.user)
        entity = await self.repository.get_by_id(
            profile_id,
            for_update=True,
        )
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        changes = payload.model_dump(exclude_unset=True, by_alias=False)
        code = changes.get("code")
        if isinstance(code, str) and code != entity.code:
            duplicate = await self.repository.get_by_code(code)
            if duplicate is not None and duplicate.id != entity.id:
                raise conflict(
                    "Section alias profile code already exists.",
                    field="code",
                )
        if changes.get("is_default") is True and not entity.is_default:
            current = await self.repository.get_default(for_update=True)
            if current is not None and current.id != entity.id:
                current.is_default = False
                current.updated_by = self.user.id
                await self.session.flush()
        if changes.get("is_active") is False and (
            changes.get("is_default", entity.is_default)
        ):
            raise business_error(
                "The default section alias profile must remain active.",
                field="isActive",
            )
        for key, value in changes.items():
            setattr(entity, key, value)
        entity.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message=(
                    "Section alias profile code or default already exists."
                ),
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_SECTION_DEFINITION,
            entity_id=entity.id,
            description=f"Section alias profile {entity.code} was updated.",
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message=(
                "Section alias profile code or default already exists."
            ),
        )
        return response


class SectionDefinitionService(MasterDataServiceBase):
    """Canonical section CRUD scoped to one alias profile."""

    entity_name = "Section Definition"
    entity_type = "section_definition"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = SectionDefinitionRepository(session)
        self.profiles = SectionAliasProfileRepository(session)

    @staticmethod
    def response(entity: SectionDefinition) -> SectionDefinitionResponse:
        return SectionDefinitionResponse(
            id=entity.id,
            profile_id=entity.profile_id,
            canonical_code=entity.canonical_code,
            display_name=entity.display_name,
            description=entity.description,
            display_order=entity.display_order,
            is_required_default=entity.is_required_default,
            is_repeatable=entity.is_repeatable,
            is_active=entity.is_active,
            alias_count=len(entity.aliases),
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list(
        self,
        *,
        profile_id: UUID | None,
        search: str | None,
        is_active: bool | None,
        is_required_default: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> SectionDefinitionListResponse:
        items, total = await self.repository.list_page(
            profile_id=profile_id,
            search=search,
            is_active=is_active,
            is_required_default=is_required_default,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return SectionDefinitionListResponse(
            items=[self.response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def get(self, definition_id: UUID) -> SectionDefinitionResponse:
        entity = await self.repository.get_by_id(definition_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def create(
        self,
        payload: SectionDefinitionCreate,
    ) -> SectionDefinitionResponse:
        _ensure_can_configure(self.user)
        profile = await self.profiles.get_by_id(payload.profile_id)
        if profile is None:
            raise business_error(
                "Section alias profile was not found.",
                field="profileId",
            )
        if not profile.is_active:
            raise business_error(
                "Section alias profile must be active.",
                field="profileId",
            )
        duplicate = await self.repository.get_by_profile_and_code(
            payload.profile_id,
            payload.canonical_code,
        )
        if duplicate is not None:
            raise conflict(
                "Canonical section code already exists in this profile.",
                field="canonicalCode",
            )
        entity = SectionDefinition(
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
                message=(
                    "Canonical section code already exists in this profile."
                ),
                field="canonicalCode",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_SECTION_DEFINITION,
            entity_id=entity.id,
            description=(
                f"Section definition {entity.canonical_code} was created."
            ),
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message=(
                "Canonical section code already exists in this profile."
            ),
            duplicate_field="canonicalCode",
        )
        return response

    async def update(
        self,
        definition_id: UUID,
        payload: SectionDefinitionUpdate,
    ) -> SectionDefinitionResponse:
        _ensure_can_configure(self.user)
        entity = await self.repository.get_by_id(
            definition_id,
            for_update=True,
        )
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        changes = payload.model_dump(exclude_unset=True, by_alias=False)
        code = changes.get("canonical_code")
        if isinstance(code, str) and code != entity.canonical_code:
            duplicate = await self.repository.get_by_profile_and_code(
                entity.profile_id,
                code,
            )
            if duplicate is not None and duplicate.id != entity.id:
                raise conflict(
                    "Canonical section code already exists in this profile.",
                    field="canonicalCode",
                )
        for key, value in changes.items():
            setattr(entity, key, value)
        entity.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message=(
                    "Canonical section code already exists in this profile."
                ),
                field="canonicalCode",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_SECTION_DEFINITION,
            entity_id=entity.id,
            description=(
                f"Section definition {entity.canonical_code} was updated."
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message=(
                "Canonical section code already exists in this profile."
            ),
            duplicate_field="canonicalCode",
        )
        return response
