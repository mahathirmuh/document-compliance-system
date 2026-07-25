"""Pre-parser request body ceilings for declared and chunked uploads."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.mark.asyncio
async def test_declared_single_upload_limit_is_path_aware_and_cors_visible(
) -> None:
    settings = get_settings().model_copy(
        update={
            "document_max_file_size_mb": 1,
            "document_batch_max_total_size_mb": 10,
        }
    )
    application = create_app(settings)
    origin = "http://localhost:5173"
    declared_size = (
        settings.document_single_upload_request_limit_bytes + 1
    )
    headers = {
        "Content-Length": str(declared_size),
        "Origin": origin,
    }
    async with AsyncClient(
        transport=ASGITransport(
            app=application,
            raise_app_exceptions=False,
        ),
        base_url="http://test",
    ) as client:
        rejected = await client.post(
            "/api/v1/document-files/upload",
            headers=headers,
            content=b"x",
        )
        batch_not_rejected_by_single_limit = await client.post(
            "/api/v1/document-files/batch-upload",
            headers=headers,
            content=b"x",
        )

    assert rejected.status_code == 413
    assert rejected.json()["success"] is False
    assert rejected.headers["access-control-allow-origin"] == origin
    assert batch_not_rejected_by_single_limit.status_code != 413


@pytest.mark.asyncio
async def test_chunked_multipart_overflow_is_rejected_while_streaming(
) -> None:
    settings = get_settings().model_copy(
        update={"document_max_file_size_mb": 1}
    )
    application = create_app(settings)
    boundary = "phase5-boundary"

    async def oversized_body() -> AsyncIterator[bytes]:
        yield (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; '
            'filename="large.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        chunk = b"x" * (1024 * 1024)
        for _ in range(4):
            yield chunk
        yield f"\r\n--{boundary}--\r\n".encode()

    origin = "http://localhost:5173"
    async with AsyncClient(
        transport=ASGITransport(
            app=application,
            raise_app_exceptions=False,
        ),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/document-files/upload",
            headers={
                "Content-Type": (
                    f"multipart/form-data; boundary={boundary}"
                ),
                "Origin": origin,
            },
            content=oversized_body(),
        )

    assert response.status_code == 413
    assert response.json()["errors"][0]["field"] == "body"
    assert response.headers["access-control-allow-origin"] == origin
