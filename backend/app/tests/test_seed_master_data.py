"""Idempotent Phase 3 master-data seed tests."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import pytest

from app.models.department import Department
from app.models.document_status import DocumentStatus
from app.models.document_type import DocumentType
from app.models.section import Section
from app.models.validation_rule import ValidationRule
from scripts.seed_master_data import seed_master_data

TestSessionFactory = async_sessionmaker[AsyncSession]


@pytest.mark.asyncio
async def test_master_data_seed_is_complete_and_idempotent(
    session_factory: TestSessionFactory,
) -> None:
    async with session_factory() as session:
        first = await seed_master_data(session)
        second = await seed_master_data(session)

        assert first == {
            "departments": 8,
            "documentTypes": 7,
            "documentStatuses": 6,
            "validationRules": 1,
        }
        assert second == {
            "departments": 0,
            "documentTypes": 0,
            "documentStatuses": 0,
            "validationRules": 0,
        }
        assert await session.scalar(select(func.count(Department.id))) == 8
        assert await session.scalar(select(func.count(DocumentType.id))) == 7
        assert await session.scalar(select(func.count(DocumentStatus.id))) == 6
        assert await session.scalar(select(func.count(Section.id))) == 0
        initial = await session.scalar(
            select(DocumentStatus).where(
                DocumentStatus.is_initial.is_(True)
            )
        )
        assert initial is not None
        assert initial.code == "DRAFT"
        default_rule = await session.scalar(
            select(ValidationRule).where(
                ValidationRule.is_default.is_(True)
            )
        )
        assert default_rule is not None
        assert default_rule.code == "DEFAULT-3LANG"
        assert default_rule.language_order_json == ["id", "en", "zh"]

