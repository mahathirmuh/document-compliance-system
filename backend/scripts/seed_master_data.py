"""Seed the minimal Phase 3 master data safely and idempotently."""

import asyncio
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import AsyncSessionFactory, dispose_engine
from app.models.department import Department
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.user import User
from app.models.validation_rule import (
    DEFAULT_LANGUAGE_ORDER,
    DEFAULT_REQUIRED_SECTIONS,
    ValidationRule,
)

DEPARTMENTS = (
    ("HRM", "Human Resource"),
    ("ICT", "Information and Communication Technology"),
    ("FNC", "Finance"),
    ("ENV", "Environmental"),
    ("PRC", "Procurement"),
    ("ACP", "Acid Plant"),
    ("CHP", "Chloride Plant"),
    ("CCP", "Copper Cathode Plant"),
)

DOCUMENT_TYPES = (
    ("SOP", "Standard Operating Procedure", "PROCEDURE"),
    ("WIN", "Work Instruction", "PROCEDURE"),
    ("POL", "Policy", "POLICY"),
    ("GUI", "Guideline", "GUIDELINE"),
    ("MAN", "Manual", "MANUAL"),
    ("FRM", "Form", "FORM"),
    ("PLN", "Plan", "PLAN"),
)

DOCUMENT_STATUSES: tuple[dict[str, Any], ...] = (
    {
        "code": "DRAFT",
        "name": "Draft",
        "display_order": 10,
        "is_initial": True,
        "is_final": False,
        "is_obsolete": False,
    },
    {
        "code": "UNDER_REVIEW",
        "name": "Under Review",
        "display_order": 20,
        "is_initial": False,
        "is_final": False,
        "is_obsolete": False,
    },
    {
        "code": "APPROVED",
        "name": "Approved",
        "display_order": 30,
        "is_initial": False,
        "is_final": False,
        "is_obsolete": False,
    },
    {
        "code": "EFFECTIVE",
        "name": "Effective",
        "display_order": 40,
        "is_initial": False,
        "is_final": True,
        "is_obsolete": False,
    },
    {
        "code": "OBSOLETE",
        "name": "Obsolete",
        "display_order": 50,
        "is_initial": False,
        "is_final": True,
        "is_obsolete": True,
    },
    {
        "code": "SUPERSEDED",
        "name": "Superseded",
        "display_order": 60,
        "is_initial": False,
        "is_final": True,
        "is_obsolete": True,
    },
)


async def _codes(
    session: AsyncSession,
    model: type[Department] | type[DocumentType] | type[DocumentStatus],
) -> set[str]:
    return set((await session.scalars(select(model.code))).all())


async def seed_master_data(session: AsyncSession) -> dict[str, int]:
    """Insert missing defaults only; never overwrite customized records."""
    settings = get_settings()
    admin = await session.scalar(
        select(User).where(
            User.email == str(settings.default_admin_email).strip().lower(),
            User.deleted_at.is_(None),
        )
    )
    actor_id = admin.id if admin is not None else None
    created = {
        "departments": 0,
        "documentTypes": 0,
        "documentStatuses": 0,
        "validationRules": 0,
    }

    department_codes = await _codes(session, Department)
    for code, name in DEPARTMENTS:
        if code in department_codes:
            continue
        session.add(
            Department(
                code=code,
                name=name,
                is_active=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        created["departments"] += 1

    document_type_codes = await _codes(session, DocumentType)
    for code, name, category in DOCUMENT_TYPES:
        if code in document_type_codes:
            continue
        session.add(
            DocumentType(
                code=code,
                name=name,
                category=category,
                requires_section=True,
                is_active=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        created["documentTypes"] += 1

    status_codes = await _codes(session, DocumentStatus)
    initial_exists = (
        await session.scalar(
            select(DocumentStatus.id).where(
                DocumentStatus.is_initial.is_(True),
                DocumentStatus.deleted_at.is_(None),
            )
        )
        is not None
    )
    for values in DOCUMENT_STATUSES:
        if values["code"] in status_codes:
            continue
        status_values = dict(values)
        if status_values["is_initial"] and initial_exists:
            status_values["is_initial"] = False
        status = DocumentStatus(
            **status_values,
            is_active=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(status)
        if status.is_initial:
            initial_exists = True
        created["documentStatuses"] += 1

    existing_rule = await session.scalar(
        select(ValidationRule).where(
            ValidationRule.code == "DEFAULT-3LANG"
        )
    )
    if existing_rule is None:
        global_default_exists = (
            await session.scalar(
                select(ValidationRule.id).where(
                    ValidationRule.document_type_id.is_(None),
                    ValidationRule.is_default.is_(True),
                    ValidationRule.deleted_at.is_(None),
                )
            )
            is not None
        )
        session.add(
            ValidationRule(
                code="DEFAULT-3LANG",
                name="Default Three-Language Validation",
                document_type_id=None,
                required_indonesian=True,
                required_english=True,
                required_chinese=True,
                minimum_indonesian_coverage=95,
                minimum_english_coverage=95,
                minimum_chinese_coverage=95,
                validate_language_order=True,
                language_order_json=list(DEFAULT_LANGUAGE_ORDER),
                validate_sections=False,
                required_sections_json=list(DEFAULT_REQUIRED_SECTIONS),
                validate_tables=False,
                minimum_compliance_score=95,
                partial_compliance_score=70,
                is_default=not global_default_exists,
                is_active=True,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        created["validationRules"] += 1

    await session.commit()
    return created


def _summary_lines(created: dict[str, int]) -> Iterable[str]:
    yield "Master data seed completed."
    for entity, count in created.items():
        yield f"{entity}: {count} created"


async def _main() -> None:
    try:
        async with AsyncSessionFactory() as session:
            created = await seed_master_data(session)
        for line in _summary_lines(created):
            print(line)
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
