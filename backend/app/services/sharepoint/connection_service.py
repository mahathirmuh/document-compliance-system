"""SharePoint connection CRUD and live Graph diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_error_mapper import GraphError
from app.integrations.microsoft_graph.sharepoint.sharepoint_drive_service import (
    SharePointDriveService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_permission_service import (
    SharePointPermissionService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_site_service import (
    SharePointSiteService,
)
from app.models.sharepoint_connection import SharePointConnection
from app.models.sharepoint_enums import SharePointConnectionStatus
from app.models.user import User
from app.repositories.sharepoint_connection_repository import (
    SharePointConnectionRepository,
)
from app.schemas.sharepoint import (
    SharePointConnectionCreateRequest,
    SharePointConnectionListResponse,
    SharePointConnectionResponse,
    SharePointConnectionTestResponse,
    SharePointConnectionUpdateRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint._common import (
    SharePointServiceBase,
    sharepoint_error,
    total_pages,
)
from app.services.sharepoint.graph_factory import create_graph_client

GraphFactory = Callable[[Settings], GraphClient]


class SharePointConnectionService(SharePointServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
        *,
        graph_factory: GraphFactory = create_graph_client,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.connections = SharePointConnectionRepository(session)
        self.graph_factory = graph_factory

    async def list(
        self,
        *,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> SharePointConnectionListResponse:
        items, total = await self.connections.list_page(
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return SharePointConnectionListResponse(
            items=[
                SharePointConnectionResponse.model_validate(item)
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages(total, page_size),
        )

    async def get(
        self,
        connection_id: UUID,
    ) -> SharePointConnectionResponse:
        connection = await self._get(connection_id)
        return SharePointConnectionResponse.model_validate(connection)

    async def create(
        self,
        payload: SharePointConnectionCreateRequest,
    ) -> SharePointConnectionResponse:
        values = payload.model_dump()
        connection = SharePointConnection(
            **values,
            status=SharePointConnectionStatus.NOT_CONFIGURED,
            is_active=True,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        try:
            if connection.is_default:
                await self.connections.clear_default()
            await self.connections.add(connection)
            await self.audit_if_registered(
                "CREATE_SHAREPOINT_CONNECTION",
                entity_type="SharePointConnection",
                entity_id=connection.id,
                description="SharePoint connection created.",
                values={
                    "name": connection.name,
                    "siteHostname": connection.site_hostname,
                    "sitePath": connection.site_path,
                    "libraryName": connection.library_name,
                    "authMode": connection.auth_mode.value,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise sharepoint_error(
                "A SharePoint connection with this name already exists.",
                code="SHAREPOINT_CONNECTION_FAILED",
                status_code=HTTPStatus.CONFLICT,
            ) from exc
        return SharePointConnectionResponse.model_validate(connection)

    async def update(
        self,
        connection_id: UUID,
        payload: SharePointConnectionUpdateRequest,
    ) -> SharePointConnectionResponse:
        connection = await self._get(connection_id, for_update=True)
        changed = payload.model_dump(exclude_unset=True)
        if changed.get("is_default"):
            await self.connections.clear_default(except_id=connection.id)
        for field, value in changed.items():
            setattr(connection, field, value)
        connection.updated_by = self.user.id
        await self.audit_if_registered(
            "UPDATE_SHAREPOINT_CONNECTION",
            entity_type="SharePointConnection",
            entity_id=connection.id,
            description="SharePoint connection updated.",
            values={
                key: (
                    value.value if hasattr(value, "value") else value
                )
                for key, value in changed.items()
            },
        )
        await self.session.commit()
        return SharePointConnectionResponse.model_validate(connection)

    async def disable(
        self,
        connection_id: UUID,
    ) -> SharePointConnectionResponse:
        connection = await self._get(connection_id, for_update=True)
        connection.is_active = False
        connection.is_default = False
        connection.status = SharePointConnectionStatus.DISABLED
        connection.updated_by = self.user.id
        await self.audit_if_registered(
            "DISABLE_SHAREPOINT_CONNECTION",
            entity_type="SharePointConnection",
            entity_id=connection.id,
            description="SharePoint connection disabled.",
        )
        await self.session.commit()
        return SharePointConnectionResponse.model_validate(connection)

    async def test(
        self,
        connection_id: UUID,
    ) -> SharePointConnectionTestResponse:
        connection = await self._get(connection_id, for_update=True)
        tested_at = datetime.now(UTC)
        graph: GraphClient | None = None
        try:
            graph = self.graph_factory(self.settings)
            site = await SharePointSiteService(graph).resolve_site(
                hostname=connection.site_hostname,
                site_path=connection.site_path,
            )
            site_id = str(site.get("id") or "")
            if not site_id:
                raise LookupError("SharePoint site did not return an ID.")
            drive = await SharePointDriveService(graph).resolve_drive(
                site_id=site_id,
                drive_id=connection.drive_id,
                library_name=connection.library_name,
            )
            drive_id = str(drive.get("id") or "")
            if not drive_id:
                raise LookupError("SharePoint drive did not return an ID.")
            permissions = await SharePointPermissionService(
                graph
            ).test_read_write(site_id=site_id, drive_id=drive_id)
            connection.site_id = site_id
            connection.drive_id = drive_id
            connection.status = SharePointConnectionStatus.CONNECTED
            connection.last_test_status = "SUCCESS"
            connection.last_test_message = (
                "Site and document library were resolved successfully."
            )
            result = SharePointConnectionTestResponse(
                connection_id=connection.id,
                status=connection.status,
                site_id=site_id,
                drive_id=drive_id,
                site_read=permissions["siteRead"],
                drive_read=permissions["driveRead"],
                tested_at=tested_at,
                message=connection.last_test_message,
            )
        except GraphError as exc:
            connection.status = self._status_for_graph_error(exc)
            connection.last_test_status = "FAILED"
            connection.last_test_message = str(exc)
            result = SharePointConnectionTestResponse(
                connection_id=connection.id,
                status=connection.status,
                tested_at=tested_at,
                message=str(exc),
            )
        except (LookupError, ValueError, RuntimeError) as exc:
            connection.status = SharePointConnectionStatus.UNAVAILABLE
            connection.last_test_status = "FAILED"
            connection.last_test_message = str(exc)
            result = SharePointConnectionTestResponse(
                connection_id=connection.id,
                status=connection.status,
                tested_at=tested_at,
                message=str(exc),
            )
        finally:
            if graph is not None:
                await graph.close()
        connection.last_tested_at = tested_at
        await self.audit_if_registered(
            "TEST_SHAREPOINT_CONNECTION",
            entity_type="SharePointConnection",
            entity_id=connection.id,
            description="SharePoint connection test completed.",
            values={"status": connection.status.value},
        )
        await self.session.commit()
        return result

    async def _get(
        self,
        connection_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointConnection:
        connection = await self.connections.get_by_id(
            connection_id,
            for_update=for_update,
        )
        if connection is None:
            raise sharepoint_error(
                "SharePoint connection was not found.",
                code="SHAREPOINT_CONNECTION_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return connection

    @staticmethod
    def _status_for_graph_error(
        error: GraphError,
    ) -> SharePointConnectionStatus:
        if error.code == "GRAPH_AUTHENTICATION_FAILED":
            return SharePointConnectionStatus.AUTHENTICATION_FAILED
        if error.code in {
            "GRAPH_AUTHORIZATION_FAILED",
            "GRAPH_ADMIN_CONSENT_REQUIRED",
        }:
            return SharePointConnectionStatus.PERMISSION_DENIED
        if error.code == "GRAPH_RATE_LIMITED":
            return SharePointConnectionStatus.DEGRADED
        return SharePointConnectionStatus.UNAVAILABLE
