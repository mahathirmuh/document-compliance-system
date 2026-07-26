"""Audited section-alias CRUD and a bounded administrative match tester."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from uuid import UUID

import regex as safe_regex
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.config import Settings, get_settings
from app.models.compliance_enums import (
    SectionAliasLanguageCode,
    SectionAliasMatchType,
)
from app.models.section_alias import (
    SectionAlias,
    normalise_section_heading,
)
from app.models.user import User
from app.repositories.section_alias_profile_repository import (
    SectionAliasProfileRepository,
)
from app.repositories.section_alias_repository import SectionAliasRepository
from app.repositories.section_definition_repository import (
    SectionDefinitionRepository,
)
from app.schemas.section_detection import (
    SectionAliasCreate,
    SectionAliasListResponse,
    SectionAliasResponse,
    SectionAliasUpdate,
    SectionAliasValues,
    SectionMatchTestRequest,
    SectionMatchTestResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.master_data.base import (
    MasterDataServiceBase,
    audit_dump,
    business_error,
    conflict,
    not_found,
)
from app.services.master_data.section_definition_service import (
    _ensure_can_configure,
)

_HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_BACKREFERENCE_PATTERN = re.compile(r"(?<!\\)\\[1-9]")
_NESTED_QUANTIFIER_PATTERN = re.compile(
    r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)\s*(?:[+*]|\{\d)"
)
_REPEATED_WILDCARD_PATTERN = re.compile(r"(?:\.\*){2,}|(?:\.\+){2,}")
_UNSAFE_EXTENSION_PATTERN = re.compile(r"\(\?(?:[=!<]|P[=>])")


def normalise_alias(
    alias_text: str,
    match_type: SectionAliasMatchType,
) -> str:
    """Return a deterministic uniqueness key for a literal or regex alias."""
    if match_type is SectionAliasMatchType.REGEX:
        return unicodedata.normalize("NFC", alias_text).strip().casefold()
    return normalise_section_heading(alias_text)


def validate_safe_regex(pattern: str, settings: Settings) -> safe_regex.Pattern:
    """Reject high-risk regex constructs before compiling a bounded pattern."""
    if len(pattern) > settings.section_alias_regex_max_length:
        raise ValueError(
            "Regex alias exceeds SECTION_ALIAS_REGEX_MAX_LENGTH."
        )
    if _BACKREFERENCE_PATTERN.search(pattern):
        raise ValueError("Regex backreferences are not allowed.")
    if _NESTED_QUANTIFIER_PATTERN.search(pattern):
        raise ValueError("Nested quantified regex groups are not allowed.")
    if _REPEATED_WILDCARD_PATTERN.search(pattern):
        raise ValueError("Repeated wildcard quantifiers are not allowed.")
    if _UNSAFE_EXTENSION_PATTERN.search(pattern):
        raise ValueError("Regex lookaround and named extensions are not allowed.")
    try:
        return safe_regex.compile(pattern, flags=safe_regex.IGNORECASE)
    except safe_regex.error as exc:
        raise ValueError(f"Regex alias is invalid: {exc.msg}.") from exc


class SectionAliasService(MasterDataServiceBase):
    """Alias CRUD plus safe, confidence-aware heading test matching."""

    entity_name = "Section Alias"
    entity_type = "section_alias"

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(session, user, metadata)
        self.repository = SectionAliasRepository(session)
        self.definitions = SectionDefinitionRepository(session)
        self.profiles = SectionAliasProfileRepository(session)
        self.settings = settings or get_settings()

    @staticmethod
    def response(entity: SectionAlias) -> SectionAliasResponse:
        definition = entity.section_definition
        return SectionAliasResponse(
            id=entity.id,
            section_definition_id=entity.section_definition_id,
            profile_id=definition.profile_id,
            canonical_code=definition.canonical_code,
            display_name=definition.display_name,
            language_code=entity.language_code,
            alias_text=entity.alias_text,
            normalised_alias=entity.normalised_alias,
            match_type=entity.match_type,
            priority=entity.priority,
            is_regex=entity.is_regex,
            is_active=entity.is_active,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _validate_alias_values(
        self,
        values: SectionAliasValues,
    ) -> str:
        if values.match_type is SectionAliasMatchType.REGEX:
            validate_safe_regex(values.alias_text, self.settings)
        return normalise_alias(values.alias_text, values.match_type)

    async def list(
        self,
        *,
        profile_id: UUID | None,
        section_definition_id: UUID | None,
        language_code: SectionAliasLanguageCode | None,
        match_type: SectionAliasMatchType | None,
        search: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> SectionAliasListResponse:
        items, total = await self.repository.list_page(
            profile_id=profile_id,
            section_definition_id=section_definition_id,
            language_code=language_code,
            match_type=match_type,
            search=search,
            is_active=is_active,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return SectionAliasListResponse(
            items=[self.response(item) for item in items],
            page=page,
            pageSize=page_size,
            totalItems=total,
            totalPages=self.total_pages(total, page_size),
        )

    async def get(self, alias_id: UUID) -> SectionAliasResponse:
        entity = await self.repository.get_by_id(alias_id)
        if entity is None:
            raise not_found(self.entity_name)
        return self.response(entity)

    async def create(
        self,
        payload: SectionAliasCreate,
    ) -> SectionAliasResponse:
        _ensure_can_configure(self.user)
        definition = await self.definitions.get_by_id(
            payload.section_definition_id
        )
        if definition is None:
            raise business_error(
                "Section definition was not found.",
                field="sectionDefinitionId",
            )
        values = SectionAliasValues.model_validate(
            payload.model_dump(
                exclude={"section_definition_id"},
                by_alias=False,
            )
        )
        normalized = self._validate_alias_values(values)
        duplicate = await self.repository.get_duplicate(
            section_definition_id=payload.section_definition_id,
            language_code=values.language_code,
            normalised_alias=normalized,
        )
        if duplicate is not None:
            raise conflict(
                "This normalized alias already exists for the language.",
                field="aliasText",
            )
        entity = SectionAlias(
            section_definition_id=payload.section_definition_id,
            **values.model_dump(by_alias=False),
            normalised_alias=normalized,
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
                    "This normalized alias already exists for the language."
                ),
                field="aliasText",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.CREATE_SECTION_ALIAS,
            entity_id=entity.id,
            description=(
                f"Section alias {entity.alias_text!r} was created."
            ),
            old_values=None,
            new_values=audit_dump(response),
            duplicate_message=(
                "This normalized alias already exists for the language."
            ),
            duplicate_field="aliasText",
        )
        return response

    async def update(
        self,
        alias_id: UUID,
        payload: SectionAliasUpdate,
    ) -> SectionAliasResponse:
        _ensure_can_configure(self.user)
        entity = await self.repository.get_by_id(alias_id, for_update=True)
        if entity is None:
            raise not_found(self.entity_name)
        old = audit_dump(self.response(entity))
        merged = {
            "language_code": entity.language_code,
            "alias_text": entity.alias_text,
            "match_type": entity.match_type,
            "priority": entity.priority,
            "is_regex": entity.is_regex,
            "is_active": entity.is_active,
        }
        merged.update(payload.model_dump(exclude_unset=True, by_alias=False))
        values = SectionAliasValues.model_validate(merged)
        normalized = self._validate_alias_values(values)
        duplicate = await self.repository.get_duplicate(
            section_definition_id=entity.section_definition_id,
            language_code=values.language_code,
            normalised_alias=normalized,
            exclude_id=entity.id,
        )
        if duplicate is not None:
            raise conflict(
                "This normalized alias already exists for the language.",
                field="aliasText",
            )
        for key, value in values.model_dump(by_alias=False).items():
            setattr(entity, key, value)
        entity.normalised_alias = normalized
        entity.updated_by = self.user.id
        try:
            await self.session.flush()
            await self.session.refresh(entity, attribute_names=["updated_at"])
            entity = await self.repository.get_by_id(entity.id) or entity
        except IntegrityError as exc:
            await self.rollback_conflict(
                exc,
                message=(
                    "This normalized alias already exists for the language."
                ),
                field="aliasText",
            )
        response = self.response(entity)
        await self.commit_audited(
            action=AuditAction.UPDATE_SECTION_ALIAS,
            entity_id=entity.id,
            description=(
                f"Section alias {entity.alias_text!r} was updated."
            ),
            old_values=old,
            new_values=audit_dump(response),
            duplicate_message=(
                "This normalized alias already exists for the language."
            ),
            duplicate_field="aliasText",
        )
        return response

    async def test_match(
        self,
        payload: SectionMatchTestRequest,
    ) -> SectionMatchTestResponse:
        profile_id = payload.profile_id
        if profile_id is None:
            profile = await self.profiles.get_default()
            if profile is None:
                return SectionMatchTestResponse(
                    matched=False,
                    confidence=0,
                    normalized_heading=normalise_section_heading(
                        payload.heading
                    ),
                )
            profile_id = profile.id
        heading = payload.heading[
            : self.settings.section_heading_max_characters
        ]
        normalized_heading = normalise_section_heading(heading)
        aliases = await self.repository.list_active_for_profile(
            profile_id,
            language_code=payload.language_code,
        )
        best: tuple[float, int, SectionAlias] | None = None
        for alias in aliases:
            confidence = self._match_confidence(
                heading=heading,
                normalized_heading=normalized_heading,
                alias=alias,
            )
            if confidence is None:
                continue
            candidate = (confidence, alias.priority, alias)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        if best is None or best[0] < self.settings.section_match_min_confidence:
            return SectionMatchTestResponse(
                matched=False,
                profile_id=profile_id,
                confidence=best[0] if best is not None else 0,
                normalized_heading=normalized_heading,
                requires_review=best is not None,
            )
        confidence, _, alias = best
        definition = alias.section_definition
        return SectionMatchTestResponse(
            matched=True,
            profile_id=profile_id,
            section_definition_id=definition.id,
            canonical_code=definition.canonical_code,
            display_name=definition.display_name,
            language_code=alias.language_code,
            matched_alias=alias.alias_text,
            match_type=alias.match_type,
            confidence=confidence,
            normalized_heading=normalized_heading,
            requires_review=confidence < 0.95,
        )

    def _match_confidence(
        self,
        *,
        heading: str,
        normalized_heading: str,
        alias: SectionAlias,
    ) -> float | None:
        if alias.match_type is SectionAliasMatchType.EXACT:
            return 1.0 if normalized_heading == alias.normalised_alias else None
        if alias.match_type is SectionAliasMatchType.PREFIX:
            return (
                0.95
                if normalized_heading.startswith(alias.normalised_alias)
                else None
            )
        if alias.match_type is SectionAliasMatchType.REGEX:
            pattern = validate_safe_regex(alias.alias_text, self.settings)
            try:
                matched = pattern.search(
                    heading,
                    timeout=(
                        self.settings.section_alias_regex_timeout_ms
                        / 1000
                    ),
                )
            except TimeoutError:
                return None
            return 0.90 if matched is not None else None
        if alias.match_type is SectionAliasMatchType.CONTAINS:
            return (
                0.90
                if alias.normalised_alias in normalized_heading
                else None
            )
        if _HAN_PATTERN.search(normalized_heading) or _HAN_PATTERN.search(
            alias.normalised_alias
        ):
            return None
        similarity = SequenceMatcher(
            None,
            normalized_heading,
            alias.normalised_alias,
            autojunk=False,
        ).ratio()
        return (
            similarity
            if similarity >= self.settings.section_fuzzy_match_threshold
            else None
        )
