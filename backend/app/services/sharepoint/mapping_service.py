"""SharePoint folder and metadata mapping application service."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharepoint_folder_mapping import SharePointFolderMapping
from app.models.sharepoint_metadata_mapping import SharePointMetadataMapping
from app.models.user import User
from app.repositories.sharepoint_connection_repository import (
    SharePointConnectionRepository,
)
from app.repositories.sharepoint_mapping_repository import (
    SharePointMappingRepository,
)
from app.schemas.sharepoint import (
    SharePointFolderMappingCreateRequest,
    SharePointFolderMappingListResponse,
    SharePointFolderMappingResponse,
    SharePointFolderMappingUpdateRequest,
    SharePointMetadataMappingCreateRequest,
    SharePointMetadataMappingListResponse,
    SharePointMetadataMappingResponse,
    SharePointMetadataMappingUpdateRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint._common import (
    SharePointServiceBase,
    sharepoint_error,
    total_pages,
)


class SharePointMappingService(SharePointServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.mappings = SharePointMappingRepository(session)
        self.connections = SharePointConnectionRepository(session)

    async def list_folders(
        self,
        *,
        connection_id: UUID | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> SharePointFolderMappingListResponse:
        items, total = await self.mappings.list_folders(
            connection_id=connection_id,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return SharePointFolderMappingListResponse(
            items=[
                SharePointFolderMappingResponse.model_validate(item)
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages(total, page_size),
        )

    async def create_folder(
        self,
        payload: SharePointFolderMappingCreateRequest,
    ) -> SharePointFolderMappingResponse:
        await self._ensure_connection(payload.sharepoint_connection_id)
        mapping = SharePointFolderMapping(
            **payload.model_dump(),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        await self.mappings.add_folder(mapping)
        await self.audit_if_registered(
            "CREATE_FOLDER_MAPPING",
            entity_type="SharePointFolderMapping",
            entity_id=mapping.id,
            description="SharePoint folder mapping created.",
            values={
                "connectionId": str(mapping.sharepoint_connection_id),
                "mappingScope": mapping.mapping_scope.value,
                "remoteFolderPath": mapping.remote_folder_path,
            },
        )
        await self.session.commit()
        return SharePointFolderMappingResponse.model_validate(mapping)

    async def update_folder(
        self,
        mapping_id: UUID,
        payload: SharePointFolderMappingUpdateRequest,
    ) -> SharePointFolderMappingResponse:
        mapping = await self.mappings.get_folder(
            mapping_id,
            for_update=True,
        )
        if mapping is None:
            raise sharepoint_error(
                "SharePoint folder mapping was not found.",
                code="SHAREPOINT_FOLDER_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        await self._ensure_connection(payload.sharepoint_connection_id)
        for key, value in payload.model_dump().items():
            setattr(mapping, key, value)
        mapping.updated_by = self.user.id
        await self.audit_if_registered(
            "UPDATE_FOLDER_MAPPING",
            entity_type="SharePointFolderMapping",
            entity_id=mapping.id,
            description="SharePoint folder mapping updated.",
        )
        await self.session.commit()
        return SharePointFolderMappingResponse.model_validate(mapping)

    async def list_metadata(
        self,
        *,
        connection_id: UUID | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> SharePointMetadataMappingListResponse:
        items, total = await self.mappings.list_metadata(
            connection_id=connection_id,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return SharePointMetadataMappingListResponse(
            items=[
                SharePointMetadataMappingResponse.model_validate(item)
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages(total, page_size),
        )

    async def create_metadata(
        self,
        payload: SharePointMetadataMappingCreateRequest,
    ) -> SharePointMetadataMappingResponse:
        await self._ensure_connection(payload.sharepoint_connection_id)
        mapping = SharePointMetadataMapping(**payload.model_dump())
        await self.mappings.add_metadata(mapping)
        await self.audit_if_registered(
            "CREATE_METADATA_MAPPING",
            entity_type="SharePointMetadataMapping",
            entity_id=mapping.id,
            description="SharePoint metadata mapping created.",
            values={
                "connectionId": str(mapping.sharepoint_connection_id),
                "documentField": mapping.document_field,
                "sharePointField": (
                    mapping.sharepoint_field_internal_name
                ),
            },
        )
        await self.session.commit()
        return SharePointMetadataMappingResponse.model_validate(mapping)

    async def update_metadata(
        self,
        mapping_id: UUID,
        payload: SharePointMetadataMappingUpdateRequest,
    ) -> SharePointMetadataMappingResponse:
        mapping = await self.mappings.get_metadata(
            mapping_id,
            for_update=True,
        )
        if mapping is None:
            raise sharepoint_error(
                "SharePoint metadata mapping was not found.",
                code="SHAREPOINT_METADATA_UPDATE_FAILED",
                status_code=HTTPStatus.NOT_FOUND,
            )
        await self._ensure_connection(payload.sharepoint_connection_id)
        for key, value in payload.model_dump().items():
            setattr(mapping, key, value)
        await self.audit_if_registered(
            "UPDATE_METADATA_MAPPING",
            entity_type="SharePointMetadataMapping",
            entity_id=mapping.id,
            description="SharePoint metadata mapping updated.",
        )
        await self.session.commit()
        return SharePointMetadataMappingResponse.model_validate(mapping)

    async def _ensure_connection(self, connection_id: UUID) -> None:
        if await self.connections.get_by_id(connection_id) is None:
            raise sharepoint_error(
                "SharePoint connection was not found.",
                code="SHAREPOINT_CONNECTION_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
