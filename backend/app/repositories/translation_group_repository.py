"""Persistence operations for translation groups and members."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember


class TranslationGroupRepository:
    """Batch group/member persistence and paginated reads."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self,
        groups: Sequence[TranslationGroup],
        *,
        batch_size: int = 1000,
    ) -> list[TranslationGroup]:
        items = list(groups)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def add_members(
        self,
        members: Sequence[TranslationGroupMember],
        *,
        batch_size: int = 1000,
    ) -> list[TranslationGroupMember]:
        items = list(members)
        for offset in range(0, len(items), batch_size):
            self.session.add_all(items[offset : offset + batch_size])
            await self.session.flush()
        return items

    async def get_by_id(
        self,
        group_id: UUID,
    ) -> TranslationGroup | None:
        statement = (
            select(TranslationGroup)
            .options(selectinload(TranslationGroup.members))
            .where(TranslationGroup.id == group_id)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_for_run(
        self,
        compliance_run_id: UUID,
        *,
        container_id: UUID | None = None,
        detected_section_id: UUID | None = None,
        is_complete: bool | None = None,
        is_order_valid: bool | None = None,
        low_confidence: bool | None = None,
        confidence_threshold: float = 0.65,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[TranslationGroup], int]:
        conditions = [TranslationGroup.compliance_run_id == compliance_run_id]
        if container_id is not None:
            conditions.append(TranslationGroup.container_id == container_id)
        if detected_section_id is not None:
            conditions.append(
                TranslationGroup.detected_section_id == detected_section_id
            )
        if is_complete is not None:
            conditions.append(TranslationGroup.is_complete.is_(is_complete))
        if is_order_valid is not None:
            conditions.append(TranslationGroup.is_order_valid.is_(is_order_valid))
        if low_confidence is True:
            conditions.append(TranslationGroup.confidence < confidence_threshold)
        elif low_confidence is False:
            conditions.append(TranslationGroup.confidence >= confidence_threshold)
        statement = select(TranslationGroup).where(*conditions)
        total = int(
            (
                await self.session.scalar(
                    select(func.count()).select_from(
                        statement.order_by(None).subquery()
                    )
                )
            )
            or 0
        )
        result = await self.session.scalars(
            statement.options(selectinload(TranslationGroup.members))
            .order_by(
                TranslationGroup.group_index,
                TranslationGroup.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.unique().all()), total

    async def count_for_run(self, compliance_run_id: UUID) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(TranslationGroup.id)).where(
                        TranslationGroup.compliance_run_id == compliance_run_id
                    )
                )
            )
            or 0
        )

    async def count_completeness_for_run(
        self,
        compliance_run_id: UUID,
    ) -> tuple[int, int]:
        """Return structural complete and incomplete counts for one run."""

        rows = await self.session.execute(
            select(
                TranslationGroup.is_complete,
                func.count(TranslationGroup.id),
            )
            .where(TranslationGroup.compliance_run_id == compliance_run_id)
            .group_by(TranslationGroup.is_complete)
        )
        counts = {bool(is_complete): int(count) for is_complete, count in rows.all()}
        return counts.get(True, 0), counts.get(False, 0)

    async def count_invalid_order_for_run(
        self,
        compliance_run_id: UUID,
    ) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(TranslationGroup.id)).where(
                        TranslationGroup.compliance_run_id == compliance_run_id,
                        TranslationGroup.is_order_valid.is_(False),
                    )
                )
            )
            or 0
        )

    async def count_members_for_run(
        self,
        compliance_run_id: UUID,
    ) -> int:
        return int(
            (
                await self.session.scalar(
                    select(func.count(TranslationGroupMember.id))
                    .join(
                        TranslationGroup,
                        TranslationGroup.id
                        == TranslationGroupMember.translation_group_id,
                    )
                    .where(TranslationGroup.compliance_run_id == compliance_run_id)
                )
            )
            or 0
        )

    async def count_members_for_run_page(
        self,
        compliance_run_id: UUID,
        *,
        container_id: UUID | None = None,
        detected_section_id: UUID | None = None,
        is_complete: bool | None = None,
        is_order_valid: bool | None = None,
        low_confidence: bool | None = None,
        confidence_threshold: float = 0.65,
        page: int,
        page_size: int,
    ) -> int:
        conditions = [TranslationGroup.compliance_run_id == compliance_run_id]
        if container_id is not None:
            conditions.append(TranslationGroup.container_id == container_id)
        if detected_section_id is not None:
            conditions.append(
                TranslationGroup.detected_section_id == detected_section_id
            )
        if is_complete is not None:
            conditions.append(TranslationGroup.is_complete.is_(is_complete))
        if is_order_valid is not None:
            conditions.append(TranslationGroup.is_order_valid.is_(is_order_valid))
        if low_confidence is True:
            conditions.append(TranslationGroup.confidence < confidence_threshold)
        elif low_confidence is False:
            conditions.append(TranslationGroup.confidence >= confidence_threshold)
        group_ids = (
            select(TranslationGroup.id)
            .where(*conditions)
            .order_by(
                TranslationGroup.group_index,
                TranslationGroup.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return int(
            (
                await self.session.scalar(
                    select(func.count(TranslationGroupMember.id)).where(
                        TranslationGroupMember.translation_group_id.in_(group_ids)
                    )
                )
            )
            or 0
        )
