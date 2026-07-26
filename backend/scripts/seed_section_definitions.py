"""Seed the default Phase 8 three-language section catalog idempotently."""

# ruff: noqa: E402 -- this executable adds the backend root before app imports.

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.database.session import AsyncSessionFactory, dispose_engine
from app.models.compliance_enums import (
    SectionAliasLanguageCode,
    SectionAliasMatchType,
)
from app.models.section_alias import (
    SectionAlias,
    normalise_section_heading,
)
from app.models.section_alias_profile import SectionAliasProfile
from app.models.section_definition import SectionDefinition
from app.models.user import User
from app.models.validation_rule import ValidationRule

PROFILE_CODE: Final = "DEFAULT-3LANG"
PROFILE_NAME: Final = "Default Three-Language Section Profile"

SECTION_SEEDS: Final = (
    (
        "TITLE",
        "Title",
        True,
        False,
        {"id": ("Judul",), "en": ("Title",), "zh": ("标题",)},
    ),
    (
        "PURPOSE",
        "Purpose",
        True,
        False,
        {"id": ("Tujuan",), "en": ("Purpose",), "zh": ("目的",)},
    ),
    (
        "SCOPE",
        "Scope",
        True,
        False,
        {"id": ("Ruang Lingkup",), "en": ("Scope",), "zh": ("范围",)},
    ),
    (
        "DEFINITION",
        "Definition",
        False,
        False,
        {
            "id": ("Definisi",),
            "en": ("Definition", "Definitions"),
            "zh": ("定义",),
        },
    ),
    (
        "REFERENCE",
        "Reference",
        False,
        False,
        {
            "id": ("Referensi", "Acuan"),
            "en": ("Reference", "References"),
            "zh": ("参考", "参考文件"),
        },
    ),
    (
        "RESPONSIBILITY",
        "Responsibility",
        True,
        False,
        {
            "id": ("Tanggung Jawab",),
            "en": ("Responsibility", "Responsibilities"),
            "zh": ("职责",),
        },
    ),
    (
        "PROCEDURE",
        "Procedure",
        True,
        False,
        {
            "id": ("Prosedur", "Tata Cara"),
            "en": ("Procedure", "Procedures"),
            "zh": ("程序", "操作程序"),
        },
    ),
    (
        "RECORDS",
        "Records",
        False,
        True,
        {
            "id": ("Rekaman", "Catatan"),
            "en": ("Records",),
            "zh": ("记录",),
        },
    ),
    (
        "ATTACHMENT",
        "Attachment",
        False,
        True,
        {
            "id": ("Lampiran",),
            "en": ("Attachment", "Attachments"),
            "zh": ("附件",),
        },
    ),
    (
        "REVISION_HISTORY",
        "Revision History",
        False,
        False,
        {
            "id": ("Riwayat Revisi",),
            "en": ("Revision History",),
            "zh": ("修订记录",),
        },
    ),
    (
        "APPROVAL",
        "Approval",
        False,
        False,
        {
            "id": ("Persetujuan",),
            "en": ("Approval",),
            "zh": ("批准",),
        },
    ),
    (
        "DISTRIBUTION",
        "Distribution",
        False,
        False,
        {
            "id": ("Distribusi",),
            "en": ("Distribution",),
            "zh": ("分发",),
        },
    ),
)


async def seed_section_definitions(
    session: AsyncSession,
) -> dict[str, int]:
    """Insert only missing profile, definitions, and exact aliases."""
    settings = get_settings()
    admin = await session.scalar(
        select(User).where(
            User.email == str(settings.default_admin_email).strip().lower(),
            User.deleted_at.is_(None),
        )
    )
    actor_id = admin.id if admin is not None else None
    created = {
        "profiles": 0,
        "definitions": 0,
        "aliases": 0,
        "rulesLinked": 0,
    }
    profile = await session.scalar(
        select(SectionAliasProfile).where(
            SectionAliasProfile.code == PROFILE_CODE
        )
    )
    if profile is None:
        default_exists = (
            await session.scalar(
                select(SectionAliasProfile.id).where(
                    SectionAliasProfile.is_default.is_(True)
                )
            )
            is not None
        )
        profile = SectionAliasProfile(
            code=PROFILE_CODE,
            name=PROFILE_NAME,
            description=(
                "Default Indonesian, English, and Chinese section aliases."
            ),
            is_default=not default_exists,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(profile)
        await session.flush()
        created["profiles"] += 1

    existing_definitions = {
        definition.canonical_code: definition
        for definition in (
            await session.scalars(
                select(SectionDefinition).where(
                    SectionDefinition.profile_id == profile.id
                )
            )
        ).all()
    }
    for display_order, seed in enumerate(SECTION_SEEDS, start=1):
        (
            canonical_code,
            display_name,
            is_required,
            is_repeatable,
            aliases,
        ) = seed
        definition = existing_definitions.get(canonical_code)
        if definition is None:
            definition = SectionDefinition(
                profile_id=profile.id,
                canonical_code=canonical_code,
                display_name=display_name,
                display_order=display_order * 10,
                is_required_default=is_required,
                is_repeatable=is_repeatable,
                is_active=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
            session.add(definition)
            await session.flush()
            existing_definitions[canonical_code] = definition
            created["definitions"] += 1
        existing_aliases = {
            (alias.language_code.value, alias.normalised_alias)
            for alias in (
                await session.scalars(
                    select(SectionAlias).where(
                        SectionAlias.section_definition_id == definition.id
                    )
                )
            ).all()
        }
        for language_code, values in aliases.items():
            language = SectionAliasLanguageCode(language_code)
            for alias_text in values:
                normalized = normalise_section_heading(alias_text)
                key = (language.value, normalized)
                if key in existing_aliases:
                    continue
                session.add(
                    SectionAlias(
                        section_definition_id=definition.id,
                        language_code=language,
                        alias_text=alias_text,
                        normalised_alias=normalized,
                        match_type=SectionAliasMatchType.EXACT,
                        priority=100,
                        is_regex=False,
                        is_active=True,
                        created_by=actor_id,
                        updated_by=actor_id,
                    )
                )
                existing_aliases.add(key)
                created["aliases"] += 1

    default_rule = await session.scalar(
        select(ValidationRule).where(
            ValidationRule.code == "DEFAULT-3LANG",
            ValidationRule.deleted_at.is_(None),
        )
    )
    if (
        default_rule is not None
        and default_rule.section_alias_profile_id is None
    ):
        default_rule.section_alias_profile_id = profile.id
        default_rule.updated_by = actor_id
        created["rulesLinked"] += 1

    await session.commit()
    return created


def _summary_lines(created: dict[str, int]) -> Iterable[str]:
    yield "Section definition seed completed."
    for entity, count in created.items():
        yield f"{entity}: {count} created or linked"


async def _main() -> None:
    try:
        async with AsyncSessionFactory() as session:
            created = await seed_section_definitions(session)
        for line in _summary_lines(created):
            print(line)
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
