"""Database-only SharePoint connection operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharepoint_connection import SharePointConnection


class SharePointConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        connection: SharePointConnection,
    ) -> SharePointConnection:
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def get_by_id(
        self,
        connection_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointConnection | None:
        statement = select(SharePointConnection).where(
            SharePointConnection.id == connection_id
        )
        if for_update:
            statement = statement.with_for_update(of=SharePointConnection)
        return await self.session.scalar(statement)

    async def get_default(self) -> SharePointConnection | None:
        return await self.session.scalar(
            select(SharePointConnection).where(
                SharePointConnection.is_default.is_(True),
                SharePointConnection.is_active.is_(True),
            )
        )

    async def clear_default(self, *, except_id: UUID | None = None) -> None:
        statement = select(SharePointConnection).where(
            SharePointConnection.is_default.is_(True)
        )
        if except_id is not None:
            statement = statement.where(SharePointConnection.id != except_id)
        for connection in await self.session.scalars(statement):
            connection.is_default = False
        await self.session.flush()

    async def list_page(
        self,
        *,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointConnection], int]:
        base = select(SharePointConnection)
        if not include_inactive:
            base = base.where(SharePointConnection.is_active.is_(True))
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(
                SharePointConnection.is_default.desc(),
                SharePointConnection.name.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total
