"""Microsoft Graph authentication, retry, streaming, and upload regressions."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from app.integrations.microsoft_graph.graph_auth_provider import (
    GraphAuthConfig,
    MsalGraphAuthProvider,
)
from app.integrations.microsoft_graph.graph_client import GraphClient
from app.integrations.microsoft_graph.graph_error_mapper import GraphError
from app.integrations.microsoft_graph.graph_pagination_service import (
    GraphPaginationService,
)
from app.integrations.microsoft_graph.graph_request_service import (
    GraphRequestService,
)
from app.integrations.microsoft_graph.graph_retry_policy import GraphRetryPolicy
from app.integrations.microsoft_graph.graph_token_cache import (
    GraphAccessToken,
    GraphTokenCache,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_download_service import (
    SharePointDownloadService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_drive_service import (
    SharePointDriveService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_file_service import (
    SharePointFileService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_folder_service import (
    SharePointFolderService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_metadata_service import (
    SharePointMetadataService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_site_service import (
    SharePointSiteService,
)
from app.integrations.microsoft_graph.sharepoint.sharepoint_upload_service import (
    GRAPH_UPLOAD_CHUNK_GRANULARITY,
    SharePointUploadService,
)
from app.services.storage.sharepoint_storage_provider import (
    SharePointStorageProvider,
)


class _TokenProvider:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        self.calls.append(force_refresh)
        return "refreshed-token" if force_refresh else "initial-token"


class _ConfidentialClient:
    def __init__(self) -> None:
        self.calls = 0

    def acquire_token_for_client(
        self,
        scopes: list[str],
    ) -> dict[str, Any]:
        assert scopes == ["https://graph.microsoft.com/.default"]
        self.calls += 1
        return {
            "access_token": f"secret-token-{self.calls}",
            "expires_in": 3600,
        }


@pytest.mark.asyncio
async def test_graph_auth_cache_keys_and_reprs_never_expose_secrets() -> None:
    client = _ConfidentialClient()
    config = GraphAuthConfig(
        tenant_id="tenant",
        client_id="client",
        client_secret="do-not-leak",
    )
    provider = MsalGraphAuthProvider(
        config,
        client_factory=lambda _: client,
    )

    first = await provider.get_access_token()
    second = await provider.get_access_token()
    refreshed = await provider.get_access_token(force_refresh=True)

    assert first == second == "secret-token-1"
    assert refreshed == "secret-token-2"
    assert client.calls == 2
    assert "do-not-leak" not in repr(config)
    assert "secret-token" not in repr(
        GraphAccessToken(
            access_token=first,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    assert GraphTokenCache.make_key(
        tenant_id="TENANT",
        client_id="CLIENT",
        scope="https://graph.microsoft.com/.default",
        auth_mode="client_secret",
    ) == GraphTokenCache.make_key(
        tenant_id="tenant",
        client_id="client",
        scope="HTTPS://GRAPH.MICROSOFT.COM/.DEFAULT",
        auth_mode="CLIENT_SECRET",
    )
    certificate = GraphAuthConfig(
        tenant_id="tenant",
        client_id="client",
        auth_mode="certificate",
        certificate_path=Path("certificate.pfx"),
        certificate_password="certificate-password",
    )
    assert "certificate-password" not in repr(certificate)


@pytest.mark.asyncio
async def test_graph_retries_retry_after_and_503_with_correlation() -> None:
    attempts = 0
    requests: list[httpx.Request] = []
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        requests.append(request)
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "3"},
                json={"error": {"code": "tooManyRequests"}},
            )
        if attempts == 2:
            return httpx.Response(
                503,
                json={"error": {"code": "serviceNotAvailable"}},
            )
        return httpx.Response(200, json={"id": "site"})

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    auth = _TokenProvider()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        requests_service = GraphRequestService(
            auth_provider=auth,
            http_client=http_client,
            retry_policy=GraphRetryPolicy(
                maximum_retries=3,
                base_seconds=1,
                maximum_seconds=10,
                jitter_ratio=0,
            ),
            sleep=fake_sleep,
        )
        result = await GraphClient(requests_service).get("/sites/example")
        counters = await requests_service.rate_limits.snapshot()

    assert result == {"id": "site"}
    assert delays == [3.0, 2.0]
    assert counters["rate_limited"] == 1
    assert counters["service_unavailable"] == 1
    assert counters["retry_count"] == 2
    assert all(
        request.headers["authorization"] == "Bearer initial-token"
        for request in requests
    )
    assert all(request.headers.get("client-request-id") for request in requests)
    assert all(
        request.headers["return-client-request-id"] == "true"
        for request in requests
    )


@pytest.mark.asyncio
async def test_graph_refreshes_one_401_and_never_retries_403() -> None:
    statuses = [401, 200]

    async def refresh_handler(request: httpx.Request) -> httpx.Response:
        status = statuses.pop(0)
        if status == 200:
            assert request.headers["authorization"] == (
                "Bearer refreshed-token"
            )
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(
            status,
            json={"error": {"code": "InvalidAuthenticationToken"}},
        )

    auth = _TokenProvider()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(refresh_handler)
    ) as http_client:
        service = GraphRequestService(
            auth_provider=auth,
            http_client=http_client,
            retry_policy=GraphRetryPolicy(maximum_retries=5),
        )
        assert await GraphClient(service).get("/me") == {"ok": True}
    assert auth.calls == [False, True]

    calls = 0

    async def forbidden_handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            403,
            headers={"request-id": "safe-request-id"},
            json={
                "error": {
                    "code": "accessDenied",
                    "message": "sensitive upstream details",
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(forbidden_handler)
    ) as http_client:
        service = GraphRequestService(
            auth_provider=_TokenProvider(),
            http_client=http_client,
            retry_policy=GraphRetryPolicy(maximum_retries=5),
        )
        with pytest.raises(GraphError) as captured:
            await GraphClient(service).get("/forbidden")
    assert calls == 1
    assert captured.value.code == "GRAPH_AUTHORIZATION_FAILED"
    assert captured.value.request_id == "safe-request-id"
    assert "sensitive upstream details" not in str(captured.value)


@pytest.mark.asyncio
async def test_graph_timeout_is_bounded_and_mapped_safely() -> None:
    calls = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("upstream timeout detail", request=request)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        service = GraphRequestService(
            auth_provider=_TokenProvider(),
            http_client=http_client,
            retry_policy=GraphRetryPolicy(
                maximum_retries=1,
                base_seconds=0.5,
                maximum_seconds=1,
                jitter_ratio=0,
            ),
            sleep=fake_sleep,
        )
        with pytest.raises(GraphError) as captured:
            await GraphClient(service).get("/slow")

    assert calls == 2
    assert delays == [0.5]
    assert captured.value.code == "GRAPH_REQUEST_TIMEOUT"
    assert "upstream timeout detail" not in str(captured.value)


@pytest.mark.asyncio
async def test_graph_pagination_and_external_download_are_bounded_and_safe() -> None:
    external_authorization: str | None = "unexpected"

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal external_authorization
        if request.url.host == "tenant.sharepoint.com":
            external_authorization = request.headers.get("authorization")
            return httpx.Response(200, content=b"private-content")
        if request.url.path.endswith("/children") and "page=2" not in str(
            request.url
        ):
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "one"}],
                    "@odata.nextLink": (
                        "https://graph.microsoft.com/v1.0/"
                        "drives/d/root/children?page=2"
                    ),
                },
            )
        if "page=2" in str(request.url):
            return httpx.Response(200, json={"value": [{"id": "two"}]})
        return httpx.Response(
            302,
            headers={
                "Location": (
                    "https://tenant.sharepoint.com/download/private-token"
                )
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GraphClient(
            GraphRequestService(
                auth_provider=_TokenProvider(),
                http_client=http_client,
            )
        )
        values = await GraphPaginationService(client).collect_values(
            "/drives/d/root/children"
        )
        content = b"".join(
            [
                chunk
                async for chunk in SharePointDownloadService(
                    client,
                    chunk_size=4,
                ).stream(drive_id="drive", item_id="item")
            ]
        )

    assert values == [{"id": "one"}, {"id": "two"}]
    assert content == b"private-content"
    assert external_authorization is None


@pytest.mark.asyncio
async def test_small_and_resumable_uploads_preserve_conflict_and_chunk_rules() -> None:
    observed_small_query: str | None = None
    chunk_ranges: list[str] = []
    upload_authorizations: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed_small_query
        if request.url.path.endswith("/content"):
            observed_small_query = request.url.params[
                "@microsoft.graph.conflictBehavior"
            ]
            return httpx.Response(
                201,
                json={"id": "small", "size": len(request.content)},
            )
        if request.url.path.endswith("/createUploadSession"):
            return httpx.Response(
                200,
                json={"uploadUrl": "https://tenant.sharepoint.com/upload/1"},
            )
        if request.url.host == "tenant.sharepoint.com":
            chunk_ranges.append(request.headers["content-range"])
            upload_authorizations.append(
                request.headers.get("authorization")
            )
            if len(chunk_ranges) == 1:
                return httpx.Response(
                    202,
                    json={"nextExpectedRanges": ["327680-"]},
                )
            return httpx.Response(
                201,
                json={
                    "id": "large",
                    "size": GRAPH_UPLOAD_CHUNK_GRANULARITY + 3,
                },
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = GraphClient(
            GraphRequestService(
                auth_provider=_TokenProvider(),
                http_client=http_client,
            )
        )
        uploader = SharePointUploadService(
            client,
            simple_upload_max_bytes=8,
            chunk_size_bytes=GRAPH_UPLOAD_CHUNK_GRANULARITY,
        )
        small = await uploader.upload(
            drive_id="drive",
            remote_path="Folder/file.pdf",
            source=io.BytesIO(b"small"),
            file_size=5,
            conflict_behavior="fail",
        )
        large_content = b"x" * (GRAPH_UPLOAD_CHUNK_GRANULARITY + 3)
        large = await uploader.upload(
            drive_id="drive",
            remote_path="Folder/large.pdf",
            source=io.BytesIO(large_content),
            file_size=len(large_content),
            conflict_behavior="rename",
        )

    assert small["id"] == "small"
    assert large["id"] == "large"
    assert observed_small_query == "fail"
    assert chunk_ranges == [
        (
            f"bytes 0-{GRAPH_UPLOAD_CHUNK_GRANULARITY - 1}/"
            f"{GRAPH_UPLOAD_CHUNK_GRANULARITY + 3}"
        ),
        (
            f"bytes {GRAPH_UPLOAD_CHUNK_GRANULARITY}-"
            f"{GRAPH_UPLOAD_CHUNK_GRANULARITY + 2}/"
            f"{GRAPH_UPLOAD_CHUNK_GRANULARITY + 3}"
        ),
    ]
    assert upload_authorizations == [None, None]


@pytest.mark.asyncio
async def test_resumable_upload_honors_server_requested_rewind() -> None:
    chunk_ranges: list[str] = []
    file_size = GRAPH_UPLOAD_CHUNK_GRANULARITY + 1

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/createUploadSession"):
            return httpx.Response(
                200,
                json={
                    "uploadUrl": "https://tenant.sharepoint.com/upload/rewind"
                },
            )
        if request.url.host == "tenant.sharepoint.com":
            chunk_ranges.append(request.headers["content-range"])
            if len(chunk_ranges) == 1:
                return httpx.Response(
                    202,
                    json={"nextExpectedRanges": ["0-"]},
                )
            if len(chunk_ranges) == 2:
                return httpx.Response(
                    202,
                    json={
                        "nextExpectedRanges": [
                            f"{GRAPH_UPLOAD_CHUNK_GRANULARITY}-"
                        ]
                    },
                )
            return httpx.Response(
                201,
                json={"id": "resumed", "size": file_size},
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        uploader = SharePointUploadService(
            GraphClient(
                GraphRequestService(
                    auth_provider=_TokenProvider(),
                    http_client=http_client,
                )
            ),
            simple_upload_max_bytes=8,
            chunk_size_bytes=GRAPH_UPLOAD_CHUNK_GRANULARITY,
        )
        result = await uploader.upload_large(
            drive_id="drive",
            remote_path="Folder/resumed.pdf",
            source=io.BytesIO(b"x" * file_size),
            file_size=file_size,
        )

    first_range = (
        f"bytes 0-{GRAPH_UPLOAD_CHUNK_GRANULARITY - 1}/{file_size}"
    )
    assert result["id"] == "resumed"
    assert chunk_ranges == [
        first_range,
        first_range,
        (
            f"bytes {GRAPH_UPLOAD_CHUNK_GRANULARITY}-"
            f"{GRAPH_UPLOAD_CHUNK_GRANULARITY}/{file_size}"
        ),
    ]


@pytest.mark.asyncio
async def test_move_and_copy_send_raw_parent_item_identifier() -> None:
    payloads: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(dict(json.loads(request.content)))
        return httpx.Response(
            200 if request.method == "PATCH" else 202,
            headers=(
                {}
                if request.method == "PATCH"
                else {"Location": "https://tenant.sharepoint.com/monitor/1"}
            ),
            json={"id": "item"} if request.method == "PATCH" else None,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        service = SharePointFileService(
            GraphClient(
                GraphRequestService(
                    auth_provider=_TokenProvider(),
                    http_client=http_client,
                )
            )
        )
        await service.move(
            drive_id="drive",
            item_id="item",
            parent_item_id="parent!with+graph=id",
        )
        monitor = await service.copy(
            drive_id="drive",
            item_id="item",
            parent_item_id="parent!with+graph=id",
        )

    assert [payload["parentReference"]["id"] for payload in payloads] == [
        "parent!with+graph=id",
        "parent!with+graph=id",
    ]
    assert monitor == "https://tenant.sharepoint.com/monitor/1"


@pytest.mark.asyncio
async def test_site_drive_folder_and_metadata_services_use_scoped_graph_paths() -> None:
    paths: list[tuple[str, str]] = []
    created_folders = 0
    metadata_payload: dict[str, Any] | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal created_folders, metadata_payload
        paths.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith(
            "/sites/tenant.sharepoint.com:/sites/compliance"
        ):
            return httpx.Response(200, json={"id": "site-id"})
        if path.endswith("/sites/site-id/drives"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "drive-id", "name": "Documents"},
                    ]
                },
            )
        if request.method == "GET" and path.endswith("/root/children"):
            return httpx.Response(200, json={"value": []})
        if (
            request.method == "GET"
            and "/items/folder-root/children" in path
        ):
            return httpx.Response(200, json={"value": []})
        if request.method == "POST" and path.endswith("/children"):
            created_folders += 1
            payload = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "id": (
                        "folder-root"
                        if created_folders == 1
                        else "folder-sub"
                    ),
                    "name": payload["name"],
                    "folder": {},
                },
            )
        if request.method == "PATCH" and path.endswith("/listItem/fields"):
            metadata_payload = dict(json.loads(request.content))
            return httpx.Response(200, json=metadata_payload)
        raise AssertionError(f"Unexpected request: {request.method} {path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        graph = GraphClient(
            GraphRequestService(
                auth_provider=_TokenProvider(),
                http_client=http_client,
            )
        )
        site = await SharePointSiteService(graph).resolve_site(
            hostname="tenant.sharepoint.com",
            site_path="/sites/compliance",
        )
        drive = await SharePointDriveService(graph).resolve_drive(
            site_id=site["id"],
            library_name="documents",
        )
        folder = await SharePointFolderService(graph).ensure_path(
            drive_id=drive["id"],
            folder_path="Root/Sub",
        )
        fields = await SharePointMetadataService(graph).update_fields(
            drive_id=drive["id"],
            item_id="item-id",
            fields={"DocumentCode": "SOP-001", "Revision": 2},
        )

    assert site["id"] == "site-id"
    assert drive["id"] == "drive-id"
    assert folder["id"] == "folder-sub"
    assert fields == {"DocumentCode": "SOP-001", "Revision": 2}
    assert metadata_payload == fields
    assert not any("/sites?" in path for _, path in paths)


def test_upload_session_expiry_is_timezone_aware() -> None:
    now = datetime(2026, 7, 26, tzinfo=UTC)
    assert SharePointUploadService.session_expired(
        "2026-07-25T23:59:59Z",
        now=now,
    )
    assert not SharePointUploadService.session_expired(
        "2026-07-26T00:00:01Z",
        now=now,
    )


@pytest.mark.asyncio
async def test_sharepoint_storage_provider_preserves_base_storage_contract() -> None:
    requests: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.method == "PUT" and request.url.path.endswith("/content"):
            return httpx.Response(
                201,
                json={
                    "id": "remote-item",
                    "size": len(request.content),
                    "eTag": "etag-1",
                },
            )
        if request.method == "GET" and "/root:/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "id": "remote-item",
                    "size": 15,
                    "eTag": "etag-1",
                },
            )
        if request.method == "GET" and request.url.path.endswith(
            "/items/remote-item/content"
        ):
            return httpx.Response(200, content=b"private-content")
        raise AssertionError(
            f"Unexpected storage request: {request.method} {request.url}"
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        graph = GraphClient(
            GraphRequestService(
                auth_provider=_TokenProvider(),
                http_client=http_client,
            )
        )
        provider = SharePointStorageProvider(
            connection_id=uuid4(),
            drive_id="drive",
            root_folder_path="Root",
            uploads=SharePointUploadService(graph),
            downloads=SharePointDownloadService(graph),
            files=SharePointFileService(graph),
            folders=SharePointFolderService(graph),
        )
        stored = await provider.store(
            io.BytesIO(b"stored-content"),
            "documents/file.pdf",
        )
        opened = await provider.open("documents/file.pdf")
        try:
            assert opened.read() == b"private-content"
        finally:
            opened.close()
        downloaded = await provider.download("documents/file.pdf")
        try:
            assert downloaded.read() == b"private-content"
        finally:
            downloaded.close()
        streamed = b"".join(
            [
                chunk
                async for chunk in provider.stream(
                    "documents/file.pdf",
                    chunk_size=3,
                )
            ]
        )
        internal_reference = provider.generate_internal_reference(
            "documents/file.pdf"
        )
        await provider.close()

    assert stored == {
        "storage_key": "documents/file.pdf",
        "storage_provider": "sharepoint",
        "size": 14,
    }
    assert streamed == b"private-content"
    assert internal_reference.startswith("sharepoint://")
    assert "documents/file.pdf" in internal_reference
    assert provider.supports_versioning
    assert provider.supports_move
    assert provider.supports_copy
    assert provider.supports_remote_metadata
    assert provider.supports_delta_sync
    assert not provider.supports_restore
    assert sum(method == "GET" for method, _ in requests) >= 6
