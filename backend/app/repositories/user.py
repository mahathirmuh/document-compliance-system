"""Persistence operations for users."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Keep user query details outside authentication business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(
        self,
        email: str,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> User | None:
        statement = select(User).where(User.email == email.strip().lower())
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        user_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> User | None:
        statement = select(User).where(User.id == user_id)
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user
