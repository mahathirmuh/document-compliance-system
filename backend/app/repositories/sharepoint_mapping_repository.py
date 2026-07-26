"""Folder and list-column mapping persistence and deterministic resolution."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharepoint_enums import FolderMappingScope
from app.models.sharepoint_folder_mapping import SharePointFolderMapping
from app.models.sharepoint_metadata_mapping import SharePointMetadataMapping

_SCOPE_RANK = {
    FolderMappingScope.SECTION_DOCUMENT_TYPE: 60,
    FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE: 50,
    FolderMappingScope.SECTION: 40,
    FolderMappingScope.DEPARTMENT: 30,
    FolderMappingScope.DOCUMENT_TYPE: 20,
    FolderMappingScope.GLOBAL: 10,
}


class SharePointMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_folder(
        self,
        mapping: SharePointFolderMapping,
    ) -> SharePointFolderMapping:
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def get_folder(
        self,
        mapping_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointFolderMapping | None:
        statement = select(SharePointFolderMapping).where(
            SharePointFolderMapping.id == mapping_id
        )
        if for_update:
            statement = statement.with_for_update(
                of=SharePointFolderMapping
            )
        return await self.session.scalar(statement)

    async def list_folders(
        self,
        *,
        connection_id: UUID | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointFolderMapping], int]:
        base = select(SharePointFolderMapping)
        if connection_id is not None:
            base = base.where(
                SharePointFolderMapping.sharepoint_connection_id
                == connection_id
            )
        if not include_inactive:
            base = base.where(SharePointFolderMapping.is_active.is_(True))
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(
                SharePointFolderMapping.priority.desc(),
                SharePointFolderMapping.created_at.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total

    async def resolve_folder(
        self,
        *,
        connection_id: UUID,
        department_id: UUID,
        section_id: UUID | None,
        document_type_id: UUID,
    ) -> SharePointFolderMapping | None:
        rows = list(
            await self.session.scalars(
                select(SharePointFolderMapping).where(
                    SharePointFolderMapping.sharepoint_connection_id
                    == connection_id,
                    SharePointFolderMapping.is_active.is_(True),
                )
            )
        )
        matches = [
            mapping
            for mapping in rows
            if self._matches_folder(
                mapping,
                department_id=department_id,
                section_id=section_id,
                document_type_id=document_type_id,
            )
        ]
        if not matches:
            return None
        return min(
            matches,
            key=lambda mapping: (
                -_SCOPE_RANK[mapping.mapping_scope],
                -mapping.priority,
                str(mapping.id),
            ),
        )

    @staticmethod
    def _matches_folder(
        mapping: SharePointFolderMapping,
        *,
        department_id: UUID,
        section_id: UUID | None,
        document_type_id: UUID,
    ) -> bool:
        scope = mapping.mapping_scope
        return {
            FolderMappingScope.GLOBAL: True,
            FolderMappingScope.DEPARTMENT: (
                mapping.department_id == department_id
            ),
            FolderMappingScope.SECTION: (
                section_id is not None and mapping.section_id == section_id
            ),
            FolderMappingScope.DOCUMENT_TYPE: (
                mapping.document_type_id == document_type_id
            ),
            FolderMappingScope.DEPARTMENT_DOCUMENT_TYPE: (
                mapping.department_id == department_id
                and mapping.document_type_id == document_type_id
            ),
            FolderMappingScope.SECTION_DOCUMENT_TYPE: (
                section_id is not None
                and mapping.section_id == section_id
                and mapping.document_type_id == document_type_id
            ),
        }[scope]

    async def add_metadata(
        self,
        mapping: SharePointMetadataMapping,
    ) -> SharePointMetadataMapping:
        self.session.add(mapping)
        await self.session.flush()
        return mapping

    async def get_metadata(
        self,
        mapping_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointMetadataMapping | None:
        statement = select(SharePointMetadataMapping).where(
            SharePointMetadataMapping.id == mapping_id
        )
        if for_update:
            statement = statement.with_for_update(
                of=SharePointMetadataMapping
            )
        return await self.session.scalar(statement)

    async def list_metadata(
        self,
        *,
        connection_id: UUID | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[SharePointMetadataMapping], int]:
        base = select(SharePointMetadataMapping)
        if connection_id is not None:
            base = base.where(
                SharePointMetadataMapping.sharepoint_connection_id
                == connection_id
            )
        if not include_inactive:
            base = base.where(SharePointMetadataMapping.is_active.is_(True))
        total = int(
            await self.session.scalar(
                select(func.count()).select_from(base.subquery())
            )
            or 0
        )
        rows = await self.session.scalars(
            base.order_by(
                SharePointMetadataMapping.document_field.asc(),
                SharePointMetadataMapping.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total

    async def active_metadata_for_connection(
        self,
        connection_id: UUID,
    ) -> list[SharePointMetadataMapping]:
        return list(
            await self.session.scalars(
                select(SharePointMetadataMapping)
                .where(
                    SharePointMetadataMapping.sharepoint_connection_id
                    == connection_id,
                    SharePointMetadataMapping.is_active.is_(True),
                )
                .order_by(SharePointMetadataMapping.document_field.asc())
            )
        )
