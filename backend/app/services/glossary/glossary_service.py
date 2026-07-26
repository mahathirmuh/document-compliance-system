"""Glossary term, translation, variant, and match-test management."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.exceptions import AuthorizationError
from app.models.glossary_enums import (
    GlossaryExceptionType,
    GlossaryLanguageCode,
    GlossaryMatchType,
    GlossaryVariantType,
)
from app.models.glossary_exception import GlossaryException
from app.models.glossary_term import GlossaryTerm
from app.models.glossary_term_variant import GlossaryTermVariant
from app.models.glossary_translation import GlossaryTranslation
from app.models.user import User
from app.repositories.glossary_exception_repository import (
    GlossaryExceptionRepository,
)
from app.repositories.glossary_profile_repository import (
    GlossaryProfileRepository,
)
from app.repositories.glossary_term_repository import GlossaryTermRepository
from app.schemas.glossary import (
    GlossaryTermCreate,
    GlossaryTermListResponse,
    GlossaryTermResponse,
    GlossaryTermUpdate,
    GlossaryTestMatchOccurrence,
    GlossaryTestMatchRequest,
    GlossaryTestMatchResponse,
    GlossaryTranslationCreate,
    GlossaryTranslationResponse,
    GlossaryTranslationUpdate,
    GlossaryVariantCreate,
    GlossaryVariantResponse,
    GlossaryVariantUpdate,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.base import (
    GlossaryServiceBase,
    glossary_error,
    glossary_not_found,
)
from app.services.glossary.contracts import (
    GlossaryMatchCandidate,
    GlossaryTextBlock,
    GlossaryValidationScope,
)
from app.services.glossary.glossary_exception_service import (
    GlossaryExceptionService,
)
from app.services.glossary.glossary_matching_service import (
    GlossaryMatchingService,
)
from app.services.glossary.matching.term_normalizer import normalize_term


class GlossaryService(GlossaryServiceBase):
    """Own all glossary concept writes; archive instead of hard delete."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
        *,
        term_max_length: int = 500,
        regex_max_length: int = 500,
        regex_timeout_ms: int = 100,
    ) -> None:
        super().__init__(session, user, metadata)
        self.terms = GlossaryTermRepository(session)
        self.profiles = GlossaryProfileRepository(session)
        self.exceptions = GlossaryExceptionRepository(session)
        self.exception_resolution = GlossaryExceptionService()
        self.matching = GlossaryMatchingService(
            term_max_length=term_max_length,
            regex_max_length=regex_max_length,
            regex_timeout_ms=regex_timeout_ms,
        )

    @staticmethod
    def variant_response(
        item: GlossaryTermVariant,
    ) -> GlossaryVariantResponse:
        return GlossaryVariantResponse.model_validate(item)

    @classmethod
    def translation_response(
        cls,
        item: GlossaryTranslation,
    ) -> GlossaryTranslationResponse:
        return GlossaryTranslationResponse(
            id=item.id,
            glossary_term_id=item.glossary_term_id,
            language_code=item.language_code,
            term_text=item.term_text,
            normalised_term=item.normalised_term,
            is_preferred=item.is_preferred,
            is_forbidden=item.is_forbidden,
            is_required=item.is_required,
            priority=item.priority,
            usage_note=item.usage_note,
            example_text=item.example_text,
            is_active=item.is_active,
            variants=[
                cls.variant_response(variant)
                for variant in item.variants
            ],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @classmethod
    def term_response(cls, item: GlossaryTerm) -> GlossaryTermResponse:
        return GlossaryTermResponse(
            id=item.id,
            glossary_profile_id=item.glossary_profile_id,
            profile_code=(
                item.profile.code if item.profile is not None else None
            ),
            term_code=item.term_code,
            concept_name=item.concept_name,
            description=item.description,
            term_type=item.term_type,
            severity=item.severity,
            is_case_sensitive=item.is_case_sensitive,
            match_whole_word=item.match_whole_word,
            allow_inflection=item.allow_inflection,
            is_regex=item.is_regex,
            is_active=item.is_active,
            notes=item.notes,
            translations=[
                cls.translation_response(translation)
                for translation in item.translations
            ],
            created_by=item.created_by,
            updated_by=item.updated_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    async def list(self, **filters: Any) -> GlossaryTermListResponse:
        page = int(filters.pop("page", 1))
        page_size = int(filters.pop("page_size", 20))
        items, total = await self.terms.list_page(
            department_ids=self.department_ids,
            page=page,
            page_size=page_size,
            **filters,
        )
        return GlossaryTermListResponse(
            items=[self.term_response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def get(self, term_id: UUID) -> GlossaryTermResponse:
        term = await self.terms.get_by_id(
            term_id,
            department_ids=self.department_ids,
        )
        if term is None:
            raise glossary_not_found("Glossary term")
        return self.term_response(term)

    async def create(
        self,
        payload: GlossaryTermCreate,
    ) -> GlossaryTermResponse:
        profile = await self.profiles.get_by_id(
            payload.glossary_profile_id,
            department_ids=self.department_ids,
        )
        if profile is None:
            raise glossary_error(
                "Glossary profile was not found.",
                field="glossaryProfileId",
            )
        if not profile.is_active:
            raise glossary_error(
                "Glossary profile must be active.",
                field="glossaryProfileId",
            )
        term = GlossaryTerm(
            **payload.model_dump(by_alias=False),
            profile=profile,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        term.translations = []
        await self.terms.add(term)
        response = self.term_response(term)
        await self.audit(
            action=AuditAction.CREATE_GLOSSARY_TERM,
            entity_type="GlossaryTerm",
            entity_id=term.id,
            description="Glossary term created.",
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="Term code already exists in this profile.",
            field="termCode",
        )
        return response

    async def update(
        self,
        term_id: UUID,
        payload: GlossaryTermUpdate,
    ) -> GlossaryTermResponse:
        term = await self._get_term(term_id, for_update=True)
        old = self.term_response(term)
        values = payload.model_dump(by_alias=False, exclude_unset=True)
        prospective_regex = values.get("is_regex", term.is_regex)
        prospective_case = values.get(
            "is_case_sensitive",
            term.is_case_sensitive,
        )
        if prospective_regex:
            for translation in term.translations:
                if translation.is_active:
                    self.matching.regex.validate(
                        translation.term_text,
                        case_sensitive=bool(prospective_case),
                    )
        for key, value in values.items():
            setattr(term, key, value)
        term.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(term, attribute_names=["updated_at"])
        response = self.term_response(term)
        await self.audit(
            action=AuditAction.UPDATE_GLOSSARY_TERM,
            entity_type="GlossaryTerm",
            entity_id=term.id,
            description="Glossary term updated.",
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="Term code already exists in this profile.",
            field="termCode",
        )
        return response

    async def archive(self, term_id: UUID) -> GlossaryTermResponse:
        return await self._set_term_active(term_id, active=False)

    async def restore(self, term_id: UUID) -> GlossaryTermResponse:
        return await self._set_term_active(term_id, active=True)

    async def add_translation(
        self,
        term_id: UUID,
        payload: GlossaryTranslationCreate,
    ) -> GlossaryTranslationResponse:
        term = await self._get_term(term_id, for_update=True)
        normalized = normalize_term(
            payload.term_text,
            case_sensitive=term.is_case_sensitive,
        )
        if term.is_regex:
            self.matching.regex.validate(
                payload.term_text,
                case_sensitive=term.is_case_sensitive,
            )
        await self._validate_translation_conflicts(
            term,
            payload.language_code,
            normalized,
            is_preferred=payload.is_preferred,
        )
        item = GlossaryTranslation(
            **payload.model_dump(by_alias=False),
            normalised_term=normalized,
            term=term,
        )
        item.variants = []
        await self.terms.add_translation(item)
        response = self.translation_response(item)
        await self.audit(
            action=AuditAction.CREATE_GLOSSARY_TRANSLATION,
            entity_type="GlossaryTranslation",
            entity_id=item.id,
            description="Glossary translation created.",
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="This normalized translation already exists.",
            field="termText",
        )
        return response

    async def update_translation(
        self,
        translation_id: UUID,
        payload: GlossaryTranslationUpdate,
    ) -> GlossaryTranslationResponse:
        item = await self.terms.get_translation(
            translation_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if item is None:
            raise glossary_not_found("Glossary translation")
        old = self.translation_response(item)
        values = payload.model_dump(by_alias=False, exclude_unset=True)
        language = cast(
            GlossaryLanguageCode,
            values.get("language_code", item.language_code),
        )
        text = cast(str, values.get("term_text", item.term_text))
        preferred = cast(
            bool,
            values.get("is_preferred", item.is_preferred),
        )
        forbidden = cast(
            bool,
            values.get("is_forbidden", item.is_forbidden),
        )
        if preferred and forbidden:
            raise glossary_error(
                "A translation cannot be preferred and forbidden.",
                field="isPreferred",
            )
        normalized = normalize_term(
            text,
            case_sensitive=item.term.is_case_sensitive,
        )
        if item.term.is_regex:
            self.matching.regex.validate(
                text,
                case_sensitive=item.term.is_case_sensitive,
            )
        await self._validate_translation_conflicts(
            item.term,
            language,
            normalized,
            is_preferred=bool(preferred),
            exclude_id=item.id,
        )
        values["normalised_term"] = normalized
        for key, value in values.items():
            setattr(item, key, value)
        await self.session.flush()
        await self.session.refresh(item, attribute_names=["updated_at"])
        response = self.translation_response(item)
        await self.audit(
            action=AuditAction.UPDATE_GLOSSARY_TRANSLATION,
            entity_type="GlossaryTranslation",
            entity_id=item.id,
            description="Glossary translation updated.",
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="This normalized translation already exists.",
            field="termText",
        )
        return response

    async def add_variant(
        self,
        translation_id: UUID,
        payload: GlossaryVariantCreate,
    ) -> GlossaryVariantResponse:
        translation = await self.terms.get_translation(
            translation_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if translation is None:
            raise glossary_not_found("Glossary translation")
        normalized = normalize_term(
            payload.variant_text,
            case_sensitive=translation.term.is_case_sensitive,
        )
        await self._validate_variant_conflict(
            translation,
            normalized,
        )
        values = payload.model_dump(by_alias=False)
        if (
            payload.variant_type
            is GlossaryVariantType.FORBIDDEN_VARIANT
        ):
            values["is_allowed"] = False
        item = GlossaryTermVariant(
            **values,
            normalised_variant=normalized,
            translation=translation,
        )
        await self.terms.add_variant(item)
        response = self.variant_response(item)
        await self.audit(
            action=AuditAction.CREATE_GLOSSARY_VARIANT,
            entity_type="GlossaryTermVariant",
            entity_id=item.id,
            description="Glossary term variant created.",
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="This normalized variant already exists.",
            field="variantText",
        )
        return response

    async def update_variant(
        self,
        variant_id: UUID,
        payload: GlossaryVariantUpdate,
    ) -> GlossaryVariantResponse:
        item = await self.terms.get_variant(
            variant_id,
            department_ids=self.department_ids,
            for_update=True,
        )
        if item is None:
            raise glossary_not_found("Glossary variant")
        old = self.variant_response(item)
        values = payload.model_dump(by_alias=False, exclude_unset=True)
        text = values.get("variant_text", item.variant_text)
        variant_type = values.get("variant_type", item.variant_type)
        normalized = normalize_term(
            text,
            case_sensitive=item.translation.term.is_case_sensitive,
        )
        await self._validate_variant_conflict(
            item.translation,
            normalized,
            exclude_id=item.id,
        )
        values["normalised_variant"] = normalized
        if variant_type is GlossaryVariantType.FORBIDDEN_VARIANT:
            values["is_allowed"] = False
        for key, value in values.items():
            setattr(item, key, value)
        await self.session.flush()
        await self.session.refresh(item, attribute_names=["updated_at"])
        response = self.variant_response(item)
        await self.audit(
            action=AuditAction.CREATE_GLOSSARY_VARIANT,
            entity_type="GlossaryTermVariant",
            entity_id=item.id,
            description="Glossary term variant updated.",
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.commit_or_conflict(
            message="This normalized variant already exists.",
            field="variantText",
        )
        return response

    async def test_match(
        self,
        payload: GlossaryTestMatchRequest,
    ) -> GlossaryTestMatchResponse:
        department_id = self._test_match_department_id(
            payload.department_id
        )
        if payload.profile_ids:
            profiles = await self.profiles.list_by_ids(
                payload.profile_ids,
                department_ids=self.department_ids,
            )
            if len(profiles) != len(payload.profile_ids):
                raise glossary_error(
                    "One or more glossary profiles were not found.",
                    field="profileIds",
                )
        else:
            profiles = await self.profiles.resolve_for_scope(
                department_id=department_id,
                document_type_id=payload.document_type_id,
            )
        profile_ids = [item.id for item in profiles]
        terms = await self.terms.list_for_profiles(profile_ids)
        block = GlossaryTextBlock(
            text=payload.text,
            language_code=payload.language_code.value,
            source_type="NATIVE_EXTRACTION",
            source_reference="TEST_MATCH",
        )
        matches, warnings = self.matching.match([block], terms)
        exceptions = await self.exceptions.list_for_terms(
            [item.glossary_term_id for item in matches],
            department_ids=self.department_ids,
        )
        scope = GlossaryValidationScope(
            department_id=department_id,
            document_type_id=payload.document_type_id,
        )
        resolved_exceptions = [
            self._test_match_exception(
                item,
                exceptions,
                scope=scope,
            )
            for item in matches
        ]
        return GlossaryTestMatchResponse(
            profile_ids=profile_ids,
            total_matches=len(matches),
            matches=[
                GlossaryTestMatchOccurrence(
                    glossary_term_id=item.glossary_term_id,
                    glossary_translation_id=(
                        item.glossary_translation_id
                    ),
                    glossary_variant_id=item.glossary_variant_id,
                    term_code=item.term_code,
                    concept_name=item.concept_name,
                    language_code=GlossaryLanguageCode(
                        item.language_code
                    ),
                    matched_text=item.matched_text,
                    normalised_matched_text=(
                        item.normalised_matched_text
                    ),
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                    match_type=GlossaryMatchType(item.match_type),
                    is_preferred=item.is_preferred,
                    is_forbidden=item.is_forbidden,
                    is_allowed_variant=item.is_allowed_variant,
                    exception_applied=exception is not None,
                    exception_id=(
                        exception.id
                        if exception is not None
                        else None
                    ),
                    exception_type=(
                        exception.exception_type
                        if exception is not None
                        else None
                    ),
                )
                for item, exception in zip(
                    matches,
                    resolved_exceptions,
                    strict=True,
                )
            ],
            warnings=warnings,
        )

    def _test_match_department_id(
        self,
        requested: UUID | None,
    ) -> UUID | None:
        allowed = self.department_ids
        if allowed is None:
            return requested
        if requested is not None and requested not in allowed:
            raise AuthorizationError(
                "The requested department is outside your glossary scope."
            )
        if requested is not None:
            return requested
        return allowed[0] if len(allowed) == 1 else None

    def _test_match_exception(
        self,
        candidate: GlossaryMatchCandidate,
        exceptions: Sequence[GlossaryException],
        *,
        scope: GlossaryValidationScope,
    ) -> GlossaryException | None:
        exception_types = [GlossaryExceptionType.IGNORE_TERM]
        if candidate.is_forbidden:
            exception_types.append(
                GlossaryExceptionType.ALLOW_FORBIDDEN_TERM
            )
        elif not candidate.is_preferred:
            exception_types.append(GlossaryExceptionType.ALLOW_VARIANT)
        for exception_type in exception_types:
            selected, _ = self.exception_resolution.select_for_match(
                exceptions,
                candidate=candidate,
                exception_type=exception_type.value,
                scope=scope,
                as_of=datetime.now(UTC).date(),
            )
            if selected is not None:
                return selected
        return None

    async def _get_term(
        self,
        term_id: UUID,
        *,
        for_update: bool,
    ) -> GlossaryTerm:
        term = await self.terms.get_by_id(
            term_id,
            department_ids=self.department_ids,
            for_update=for_update,
        )
        if term is None:
            raise glossary_not_found("Glossary term")
        return term

    async def _set_term_active(
        self,
        term_id: UUID,
        *,
        active: bool,
    ) -> GlossaryTermResponse:
        term = await self._get_term(term_id, for_update=True)
        old = self.term_response(term)
        term.is_active = active
        term.updated_by = self.user.id
        await self.session.flush()
        await self.session.refresh(term, attribute_names=["updated_at"])
        response = self.term_response(term)
        await self.audit(
            action=(
                AuditAction.UPDATE_GLOSSARY_TERM
                if active
                else AuditAction.ARCHIVE_GLOSSARY_TERM
            ),
            entity_type="GlossaryTerm",
            entity_id=term.id,
            description=(
                "Glossary term restored."
                if active
                else "Glossary term archived."
            ),
            old_values=old.model_dump(mode="json", by_alias=True),
            new_values=response.model_dump(mode="json", by_alias=True),
        )
        await self.session.commit()
        return response

    async def _validate_translation_conflicts(
        self,
        term: GlossaryTerm,
        language_code: GlossaryLanguageCode,
        normalized: str,
        *,
        is_preferred: bool,
        exclude_id: UUID | None = None,
    ) -> None:
        duplicate = await self.terms.find_translation_conflict(
            term_id=term.id,
            language_code=language_code,
            normalised_term=normalized,
            exclude_id=exclude_id,
        )
        if duplicate is not None:
            raise glossary_error(
                "This normalized translation already exists.",
                field="termText",
                status_code=409,
            )
        if is_preferred and any(
            translation.is_active
            and translation.is_preferred
            and translation.language_code == language_code
            and translation.id != exclude_id
            for translation in term.translations
        ):
            raise glossary_error(
                "Only one preferred translation is allowed per language.",
                field="isPreferred",
                status_code=409,
            )

    async def _validate_variant_conflict(
        self,
        translation: GlossaryTranslation,
        normalized: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        if normalized == translation.normalised_term:
            raise glossary_error(
                "Variant must differ from its translation.",
                field="variantText",
            )
        duplicate = await self.terms.find_variant_conflict(
            translation_id=translation.id,
            normalised_variant=normalized,
            exclude_id=exclude_id,
        )
        if duplicate is not None:
            raise glossary_error(
                "This normalized variant already exists.",
                field="variantText",
                status_code=409,
            )
