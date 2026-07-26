"""Validation-rule business rules and audited transactions."""

from __future__ import annotations

import builtins
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.user import User
from app.models.validation_rule import QualityScoreMode, ValidationRule
from app.repositories.document_type_repository import DocumentTypeRepository
from app.repositories.section_alias_profile_repository import (
    SectionAliasProfileRepository,
)
from app.repositories.validation_rule_repository import ValidationRuleRepository
from app.schemas.master_data import MasterDataOption
from app.schemas.validation_rule import (
    ValidationRuleCreate,
    ValidationRuleListResponse,
    ValidationRuleResponse,
    ValidationRuleUpdate,
    ValidationRuleValues,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import (
    MasterDataServiceBase,
    audit_dump,
    business_error,
    conflict,
    not_found,
)


class ValidationRuleService(MasterDataServiceBase):
    entity_name = "Validation Rule"
    entity_type = "validation_rule"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = ValidationRuleRepository(session)
        self.document_types = DocumentTypeRepository(session)
        self.section_alias_profiles = SectionAliasProfileRepository(session)

    @staticmethod
    def response(entity: ValidationRule) -> ValidationRuleResponse:
        document_type = (
            MasterDataOption.model_validate(entity.document_type)
            if entity.document_type is not None
            else None
        )
        section_alias_profile = (
            MasterDataOption.model_validate(entity.section_alias_profile)
            if entity.section_alias_profile is not None
            else None
        )
        return ValidationRuleResponse(
            id=entity.id,
            name=entity.name,
            code=entity.code,
            description=entity.description,
            document_type_id=entity.document_type_id,
            document_type=document_type,
            required_indonesian=entity.required_indonesian,
            required_english=entity.required_english,
            required_chinese=entity.required_chinese,
            validate_document_code=entity.validate_document_code,
            validate_language_presence=entity.validate_language_presence,
            validate_language_coverage=entity.validate_language_coverage,
            validate_container_completeness=(entity.validate_container_completeness),
            minimum_indonesian_coverage=entity.minimum_indonesian_coverage,
            minimum_english_coverage=entity.minimum_english_coverage,
            minimum_chinese_coverage=entity.minimum_chinese_coverage,
            validate_language_order=entity.validate_language_order,
            language_order=list(entity.language_order_json),
            validate_sections=entity.validate_sections,
            required_sections=list(entity.required_sections_json),
            validate_tables=entity.validate_tables,
            validate_translation_groups=(entity.validate_translation_groups),
            validate_cells=entity.validate_cells,
            required_languages=list(entity.required_languages_json),
            section_alias_profile_id=entity.section_alias_profile_id,
            section_alias_profile=section_alias_profile,
            minimum_language_block_coverage=dict(
                entity.minimum_language_block_coverage_json
            ),
            minimum_language_character_coverage=dict(
                entity.minimum_language_character_coverage_json
            ),
            maximum_unknown_block_percentage=float(
                entity.maximum_unknown_block_percentage
            ),
            maximum_mixed_block_percentage=float(entity.maximum_mixed_block_percentage),
            document_code_weight=float(entity.document_code_weight),
            language_presence_weight=float(entity.language_presence_weight),
            language_coverage_weight=float(entity.language_coverage_weight),
            section_completeness_weight=float(entity.section_completeness_weight),
            language_order_weight=float(entity.language_order_weight),
            translation_group_weight=float(entity.translation_group_weight),
            table_completeness_weight=float(entity.table_completeness_weight),
            translation_similarity_weight=float(entity.translation_similarity_weight),
            glossary_compliance_weight=float(entity.glossary_compliance_weight),
            quality_score_mode=QualityScoreMode(entity.quality_score_mode),
            critical_finding_score_cap=float(entity.critical_finding_score_cap),
            major_finding_penalty=float(entity.major_finding_penalty),
            minor_finding_penalty=float(entity.minor_finding_penalty),
            compliant_score=float(entity.compliant_score),
            partially_compliant_score=float(entity.partially_compliant_score),
            needs_review_score=float(entity.needs_review_score),
            fail_on_missing_required_language=(
                entity.fail_on_missing_required_language
            ),
            fail_on_missing_required_section=(entity.fail_on_missing_required_section),
            fail_on_critical_finding=entity.fail_on_critical_finding,
            validation_options=dict(entity.validation_options_json),
            minimum_compliance_score=entity.minimum_compliance_score,
            partial_compliance_score=entity.partial_compliance_score,
            is_default=entity.is_default,
            is_active=entity.is_active,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def values_from_entity(entity: ValidationRule) -> dict[str, Any]:
        return {
            "name": entity.name,
            "code": entity.code,
            "description": entity.description,
            "document_type_id": entity.document_type_id,
            "required_indonesian": entity.required_indonesian,
            "required_english": entity.required_english,
            "required_chinese": entity.required_chinese,
            "validate_document_code": entity.validate_document_code,
            "validate_language_presence": entity.validate_language_presence,
            "validate_language_coverage": entity.validate_language_coverage,
            "validate_container_completeness": (entity.validate_container_completeness),
            "minimum_indonesian_coverage": entity.minimum_indonesian_coverage,
            "minimum_english_coverage": entity.minimum_english_coverage,
            "minimum_chinese_coverage": entity.minimum_chinese_coverage,
            "validate_language_order": entity.validate_language_order,
            "language_order": list(entity.language_order_json),
            "validate_sections": entity.validate_sections,
            "required_sections": list(entity.required_sections_json),
            "validate_tables": entity.validate_tables,
            "validate_translation_groups": (entity.validate_translation_groups),
            "validate_cells": entity.validate_cells,
            "required_languages": list(entity.required_languages_json),
            "section_alias_profile_id": entity.section_alias_profile_id,
            "minimum_language_block_coverage": dict(
                entity.minimum_language_block_coverage_json
            ),
            "minimum_language_character_coverage": dict(
                entity.minimum_language_character_coverage_json
            ),
            "maximum_unknown_block_percentage": float(
                entity.maximum_unknown_block_percentage
            ),
            "maximum_mixed_block_percentage": float(
                entity.maximum_mixed_block_percentage
            ),
            "document_code_weight": float(entity.document_code_weight),
            "language_presence_weight": float(entity.language_presence_weight),
            "language_coverage_weight": float(entity.language_coverage_weight),
            "section_completeness_weight": float(entity.section_completeness_weight),
            "language_order_weight": float(entity.language_order_weight),
            "translation_group_weight": float(entity.translation_group_weight),
            "table_completeness_weight": float(entity.table_completeness_weight),
            "translation_similarity_weight": float(
                entity.translation_similarity_weight
            ),
            "glossary_compliance_weight": float(entity.glossary_compliance_weight),
            "quality_score_mode": entity.quality_score_mode,
            "critical_finding_score_cap": float(entity.critical_finding_score_cap),
            "major_finding_penalty": float(entity.major_finding_penalty),
            "minor_finding_penalty": float(entity.minor_finding_penalty),
            "compliant_score": float(entity.compliant_score),
            "partially_compliant_score": float(entity.partially_compliant_score),
            "needs_review_score": float(entity.needs_review_score),
            "fail_on_missing_required_language": (
                entity.fail_on_missing_required_language
            ),
            "fail_on_missing_required_section": (
                entity.fail_on_missing_required_section
            ),
            "fail_on_critical_finding": entity.fail_on_critical_finding,
            "validation_options": dict(entity.validation_options_json),
            "minimum_compliance_score": entity.minimum_compliance_score,
            "partial_compliance_score": entity.partial_compliance_score,
            "is_default": entity.is_default,
            "is_active": entity.is_active,
        }

    async def _validate_scope(
        self,
        values: ValidationRuleValues,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        if values.document_type_id is not None:
            document_type = await self.document_types.get_by_id(values.document_type_id)
            if document_type is None:
                raise business_error(
                    "Document type was not found.",
                    field="documentTypeId",
                )
        if values.section_alias_profile_id is not None:
            profile = await self.section_alias_profiles.get_by_id(
                values.section_alias_profile_id
            )
            if profile is None:
                raise business_error(
                    "Section alias profile was not found.",
                    field="sectionAliasProfileId",
                )
            if not profile.is_active:
                raise business_error(
                    "Section alias profile must be active.",
                    field="sectionAliasProfileId",
                )
        if values.is_default:
            existing = await self.repository.get_default(
                values.document_type_id,
                exclude_id=exclude_id,
                for_update=True,
            )
            if existing is not None:
                scope = (
                    "global"
                    if values.document_type_id is None
                    else "for this document type"
                )
                raise conflict(
                    f"A default validation rule already exists {scope}.",
                    field="isDefault",
                    title="Validation Rule could not be saved.",
                )

    @staticmethod
    def entity_values(values: ValidationRuleValues) -> dict[str, Any]:
        data = values.model_dump(by_alias=False)
        data["language_order_json"] = data.pop("language_order")
        data["required_sections_json"] = data.pop("required_sections")
        data["required_languages_json"] = data.pop("required_languages")
        data["minimum_language_block_coverage_json"] = data.pop(
            "minimum_language_block_coverage"
        )
        data["minimum_language_character_coverage_json"] = data.pop(
            "minimum_language_character_coverage"
        )
        data["validation_options_json"] = data.pop("validation_options")
        return data

    async def _sync_document_type_default(
        self,
        entity: ValidationRule,
        *,
        old_document_type_id: UUID | None = None,
    ) -> None:
        if old_document_type_id is not None and (
            old_document_type_id != entity.document_type_id or not entity.is_default
        ):
            old_type = await self.document_types.get_by_id(
                old_document_type_id,
                for_update=True,
            )
            if (
                old_type is not None
                and old_type.default_validation_rule_id == entity.id
            ):
                old_type.default_validation_rule_id = None
                old_type.updated_by = self.user.id
        if entity.document_type_id is not None and entity.is_default:
            document_type = await self.document_types.get_by_id(
                entity.document_type_id,
                for_update=True,
            )
            if document_type is not None:
                document_type.default_validation_rule_id = entity.id
                document_type.updated_by = self.user.id

    async def list(
        self,
        *,
        document_type_id: UUID | None,
        search: str | None,
        is_active: bool | None,
        is_default: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> ValidationRuleListResponse:
        items, total = await self.repository.list_page(
            document_type_id=document_type_id,
            search=search,
            is_active=is_active,
            is_default=is_default,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return ValidationRuleListResponse(
            items=[self.response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def get(self, entity_id: UUID) -> ValidationRuleResponse:
        entity = await self.repository.get_by_id(entity_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def options(
        self, *, active_only: bool = True
    ) -> builtins.list[MasterDataOption]:
        entities = await self.repository.options(active_only=active_only)
        return [MasterDataOption.model_validate(entity) for entity in entities]

    async def create(
        self,
        payload: ValidationRuleCreate,
    ) -> ValidationRuleResponse:
        if await self.repository.get_by_code(payload.code) is not None:
            raise conflict(
                "Validation rule code already exists.",
                field="code",
                title="Validation Rule could not be created.",
            )
        # The request schema has already synchronized Phase 3 and Phase 8
        # mirrors using the fields actually supplied by the client. Rebuilding
        # it from a full dump would erase that field provenance.
        values = payload
        await self._validate_scope(values)
        entity = ValidationRule(
            **self.entity_values(values),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            await self.repository.add(entity)
            await self._sync_document_type_default(entity)
            await self.session.flush()
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message=("Validation rule code or default scope already exists."),
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_VALIDATION_RULE,
            entity_id=entity.id,
            description=f"Validation rule {entity.code} was created.",
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message=("Validation rule code or default scope already exists."),
        )
        return response

    async def update(
        self,
        entity_id: UUID,
        payload: ValidationRuleUpdate,
    ) -> ValidationRuleResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        merged = self.values_from_entity(entity)
        changes = payload.model_dump(exclude_unset=True, by_alias=False)
        if "is_active" in changes and changes["is_active"] != entity.is_active:
            raise business_error(
                "Use the dedicated activate or deactivate endpoint to "
                "change validation rule status.",
                field="isActive",
            )
        if "is_default" in changes and changes["is_default"] != entity.is_default:
            raise business_error(
                "Use the set-default endpoint to change the default validation rule.",
                field="isDefault",
            )
        merged.update(changes)
        values = ValidationRuleValues.model_validate(
            merged,
            context={
                "validation_rule_explicit_fields": frozenset(changes),
            },
        )
        if values.code != entity.code:
            duplicate = await self.repository.get_by_code(values.code)
            if duplicate is not None and duplicate.id != entity.id:
                raise conflict(
                    "Validation rule code already exists.",
                    field="code",
                    title="Validation Rule could not be updated.",
                )
        await self._validate_scope(values, exclude_id=entity.id)
        old_document_type_id = entity.document_type_id
        for key, value in self.entity_values(values).items():
            setattr(entity, key, value)
        entity.updated_by = self.user.id
        try:
            await self._sync_document_type_default(
                entity,
                old_document_type_id=old_document_type_id,
            )
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message=("Validation rule code or default scope already exists."),
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_VALIDATION_RULE,
            entity_id=entity.id,
            description=f"Validation rule {entity.code} was updated.",
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message=("Validation rule code or default scope already exists."),
        )
        return response

    async def set_active(
        self,
        entity_id: UUID,
        *,
        active: bool,
    ) -> ValidationRuleResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        if not active and entity.is_default:
            raise business_error(
                "A default validation rule cannot be deactivated.",
                field="isActive",
            )
        old = audit_dump(self.response(entity))
        entity.is_active = active
        entity.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(entity, attribute_names=["updated_at"])
        response = self.response(entity)
        await self.commit_audited(
            action=(
                AuditAction.ACTIVATE_VALIDATION_RULE
                if active
                else AuditAction.DEACTIVATE_VALIDATION_RULE
            ),
            entity_id=entity.id,
            description=(
                f"Validation rule {entity.code} was "
                f"{'activated' if active else 'deactivated'}."
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message="Validation rule state could not be changed.",
            duplicate_field=None,
        )
        return response

    async def set_default(self, entity_id: UUID) -> ValidationRuleResponse:
        entity = await self.repository.get_by_id(entity_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        current = await self.repository.get_default(
            entity.document_type_id,
            exclude_id=entity.id,
            for_update=True,
        )
        replaced_id = None
        if current is not None:
            replaced_id = current.id
            current.is_default = False
            current.updated_by = self.user.id
            # Flush the previous default first so PostgreSQL/SQLite partial
            # unique indexes never observe two defaults in one scope.
            await self.session.flush()
        entity.is_default = True
        entity.is_active = True
        entity.updated_by = self.user.id
        await self._sync_document_type_default(entity)
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message="Default validation rule could not be changed.",
                field="isDefault",
            )
        response = self.response(entity)
        new_values = audit_dump(response)
        new_values["replacedDefaultId"] = (
            str(replaced_id) if replaced_id is not None else None
        )
        await self.commit_audited(
            action=AuditAction.SET_DEFAULT_VALIDATION_RULE,
            entity_id=entity.id,
            description=f"Validation rule {entity.code} was set as default.",
            old_values=old,
            new_values=new_values,
            duplicate_message="Default validation rule could not be changed.",
            duplicate_field="isDefault",
        )
        return response
