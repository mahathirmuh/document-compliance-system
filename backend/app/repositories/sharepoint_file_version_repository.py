"""SharePoint remote-file version persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharepoint_file_version import SharePointFileVersion


class SharePointFileVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        version: SharePointFileVersion,
    ) -> SharePointFileVersion:
        existing = await self.session.scalar(
            select(SharePointFileVersion).where(
                SharePointFileVersion.document_file_id
                == version.document_file_id,
                SharePointFileVersion.remote_drive_id
                == version.remote_drive_id,
                SharePointFileVersion.remote_item_id
                == version.remote_item_id,
                SharePointFileVersion.remote_version_id
                == version.remote_version_id,
            )
        )
        if existing is not None:
            return existing
        self.session.add(version)
        await self.session.flush()
        return version

    async def list_page(
        self,
        document_file_id: UUID,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointFileVersion], int]:
        base = select(SharePointFileVersion).where(
            SharePointFileVersion.document_file_id == document_file_id
        )
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(SharePointFileVersion.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total
