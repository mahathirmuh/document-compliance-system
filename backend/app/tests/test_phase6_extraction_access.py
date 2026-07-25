"""Focused Phase 6 permission, scope, duplicate, and API validation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.core.exceptions import ApplicationError, AuthorizationError
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
from app.models.extracted_table import ExtractedTable
from app.models.extraction_job import (
    ExtractionJob,
    ExtractionJobStatus,
    ExtractionJobType,
)
from app.models.extraction_run import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractorType,
)
from app.models.user import User
from app.services.auth.auth_service import RequestMetadata
from app.services.auth.token_service import TokenService
from app.services.extraction.extraction_content_service import (
    _plain_text_snippet,
)
from app.services.extraction.extraction_job_service import (
    ExtractionJobService,
)


def _graph(
    department_id: UUID,
    *,
    suffix: str,
    hash_character: str,
) -> tuple[Document, DocumentRevision, DocumentFile]:
    document = Document(
        company_code="MTI",
        department_id=department_id,
        document_type_id=uuid4(),
        document_number=suffix,
        base_document_code=f"MTI-HRM-POL-{suffix}",
        title=f"Scoped Policy {suffix}",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code=f"MTI-HRM-POL-{suffix}_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    document_file = DocumentFile(
        document=document,
        revision=revision,
        original_filename=f"MTI-HRM-POL-{suffix}_Rev.000.pdf",
        sanitized_filename=f"MTI-HRM-POL-{suffix}_Rev.000.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=100,
        sha256_hash=hash_character * 64,
        storage_key=f"documents/originals/access/{suffix}.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    return document, revision, document_file


def _job(
    graph: tuple[Document, DocumentRevision, DocumentFile],
) -> ExtractionJob:
    document, revision, document_file = graph
    return ExtractionJob(
        document=document,
        revision=revision,
        document_file=document_file,
        job_type=ExtractionJobType.INITIAL_EXTRACTION,
        status=ExtractionJobStatus.QUEUED,
        progress=0,
    )


def _service(session, user: User) -> ExtractionJobService:
    return ExtractionJobService(
        session,
        get_settings(),
        user,
        RequestMetadata(ip_address="127.0.0.1", user_agent="pytest"),
    )


def _headers(user: User, token_service: TokenService) -> dict[str, str]:
    token = token_service.create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


async def _seed_extraction_history(
    session_factory: Any,
    *,
    department_id: UUID,
    requester: User,
    suffix: str,
    raw_text: str = "Current extracted content",
) -> tuple[UUID, UUID, UUID]:
    graph = _graph(
        department_id,
        suffix=suffix,
        hash_character=suffix[-1].lower(),
    )
    document, revision, document_file = graph
    async with session_factory() as session:
        session.add_all(graph)
        await session.flush()
        old_job = ExtractionJob(
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            job_type=ExtractionJobType.INITIAL_EXTRACTION,
            status=ExtractionJobStatus.COMPLETED,
            progress=100,
            requested_by=requester.id,
        )
        current_job = ExtractionJob(
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            job_type=ExtractionJobType.RE_EXTRACTION,
            status=ExtractionJobStatus.COMPLETED,
            progress=100,
            requested_by=requester.id,
        )
        session.add_all((old_job, current_job))
        await session.flush()
        old_run = ExtractionRun(
            extraction_job_id=old_job.id,
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            extractor_type=ExtractorType.PDF,
            extractor_version="phase6-test",
            status=ExtractionRunStatus.COMPLETED,
            source_sha256_hash=document_file.sha256_hash,
            source_file_size=document_file.file_size,
            content_hash="e" * 64,
        )
        current_run = ExtractionRun(
            extraction_job_id=current_job.id,
            document_id=document.id,
            document_revision_id=revision.id,
            document_file_id=document_file.id,
            extractor_type=ExtractorType.PDF,
            extractor_version="phase6-test",
            status=ExtractionRunStatus.COMPLETED,
            source_sha256_hash=document_file.sha256_hash,
            source_file_size=document_file.file_size,
            content_hash="f" * 64,
            total_pages=1,
            total_tables=1,
            total_characters=len(raw_text),
        )
        session.add_all((old_run, current_run))
        await session.flush()
        container = ExtractedContainer(
            extraction_run_id=current_run.id,
            container_type=ExtractedContainerType.PDF_PAGE,
            container_index=1,
            name="Page 1",
            raw_text=raw_text,
            normalised_text=raw_text,
            character_count=len(raw_text),
            word_count=len(raw_text.split()),
        )
        session.add(container)
        await session.flush()
        session.add(
            ExtractedTable(
                extraction_run_id=current_run.id,
                container_id=container.id,
                source_reference="page:1:table:1",
                table_index=1,
                row_count=1,
                column_count=1,
                raw_text=raw_text,
            )
        )
        document_file.latest_extraction_run_id = current_run.id
        await session.commit()
        return document_file.id, old_run.id, current_run.id


@pytest.mark.asyncio
async def test_job_list_and_detail_are_fail_closed_to_user_department(
    session_factory,
    create_user,
) -> None:
    own_department_id = uuid4()
    other_department_id = uuid4()
    user = await create_user(
        email="department.scope@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=own_department_id,
    )
    own_graph = _graph(
        own_department_id,
        suffix="061",
        hash_character="a",
    )
    other_graph = _graph(
        other_department_id,
        suffix="062",
        hash_character="b",
    )
    own_job = _job(own_graph)
    other_job = _job(other_graph)

    async with session_factory() as session:
        session.add_all([*own_graph, own_job, *other_graph, other_job])
        await session.commit()

        jobs = await _service(session, user).list(
            search=None,
            department_id=None,
            document_id=None,
            revision_id=None,
            document_file_id=None,
            extractor_type=None,
            statuses=None,
            requested_by=None,
            requested_from=None,
            requested_to=None,
            page=1,
            page_size=20,
            sort_by="requestedAt",
            sort_order="desc",
        )
        assert jobs.total_items == 1
        assert jobs.items[0].id == own_job.id

        with pytest.raises(ApplicationError) as error:
            await _service(session, user).get(other_job.id)
        assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_active_duplicate_is_rejected_before_dispatch(
    session_factory,
    create_user,
) -> None:
    department_id = uuid4()
    user = await create_user(
        email="duplicate.scope@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=department_id,
    )
    graph = _graph(
        department_id,
        suffix="063",
        hash_character="c",
    )
    active_job = _job(graph)

    async with session_factory() as session:
        session.add_all([*graph, active_job])
        await session.commit()

        with pytest.raises(ApplicationError) as error:
            await _service(session, user).start(
                graph[2].id,
                force=False,
            )
        assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_department_user_cannot_cancel_extraction(
    session_factory,
    create_user,
) -> None:
    user = await create_user(
        email="cancel.scope@example.com",
        role=UserRole.DEPARTMENT_USER,
        department_id=uuid4(),
    )
    async with session_factory() as session:
        with pytest.raises(AuthorizationError):
            await _service(session, user).cancel(uuid4())


@pytest.mark.asyncio
async def test_viewer_cannot_list_extraction_queue(
    session_factory,
    create_user,
) -> None:
    user = await create_user(
        email="viewer.queue@example.com",
        role=UserRole.VIEWER,
    )
    async with session_factory() as session:
        with pytest.raises(AuthorizationError):
            await _service(session, user).list(
                search=None,
                department_id=None,
                document_id=None,
                revision_id=None,
                document_file_id=None,
                extractor_type=None,
                statuses=None,
                requested_by=None,
                requested_from=None,
                requested_to=None,
                page=1,
                page_size=20,
                sort_by="requestedAt",
                sort_order="desc",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["x", "x" * 201])
async def test_search_query_enforces_phase6_length_contract(
    api_client: AsyncClient,
    create_user,
    query: str,
) -> None:
    await create_user(
        email="viewer.search@example.com",
        role=UserRole.VIEWER,
    )
    login = await api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "viewer.search@example.com",
            "password": "Valid123",
        },
    )
    token = login.json()["data"]["accessToken"]

    response = await api_client.get(
        f"/api/v1/extraction-runs/{uuid4()}/search",
        params={"q": query},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_content_only_viewer_cannot_address_superseded_run(
    api_client: AsyncClient,
    create_user,
    token_service: TokenService,
    session_factory,
) -> None:
    department_id = uuid4()
    viewer = await create_user(
        email="viewer.latest-only@example.com",
        role=UserRole.VIEWER,
        department_id=department_id,
    )
    file_id, old_run_id, current_run_id = await _seed_extraction_history(
        session_factory,
        department_id=department_id,
        requester=viewer,
        suffix="070",
    )
    headers = _headers(viewer, token_service)

    latest = await api_client.get(
        f"/api/v1/document-files/{file_id}/extraction",
        headers=headers,
    )
    assert latest.status_code == 200
    assert latest.json()["data"]["runId"] == str(current_run_id)

    current = await api_client.get(
        f"/api/v1/extraction-runs/{current_run_id}",
        headers=headers,
    )
    assert current.status_code == 200

    requests = (
        (f"/api/v1/extraction-runs/{old_run_id}", None),
        (f"/api/v1/extraction-runs/{old_run_id}/containers", None),
        (f"/api/v1/extraction-runs/{old_run_id}/blocks", None),
        (f"/api/v1/extraction-runs/{old_run_id}/tables", None),
        (
            f"/api/v1/extraction-runs/{old_run_id}/search",
            {"q": "content"},
        ),
    )
    for path, params in requests:
        response = await api_client.get(
            path,
            headers=headers,
            params=params,
        )
        assert response.status_code == 404
        assert "outside your access scope" in response.text


@pytest.mark.asyncio
async def test_viewer_current_file_guards_and_history_role_scope(
    api_client: AsyncClient,
    create_user,
    token_service: TokenService,
    session_factory,
) -> None:
    department_id = uuid4()
    viewer = await create_user(
        email="viewer.file-state@example.com",
        role=UserRole.VIEWER,
        department_id=department_id,
    )
    reviewer = await create_user(
        email="reviewer.history@example.com",
        role=UserRole.REVIEWER,
        department_id=department_id,
    )
    outside_reviewer = await create_user(
        email="reviewer.outside@example.com",
        role=UserRole.REVIEWER,
        department_id=uuid4(),
    )
    file_id, old_run_id, current_run_id = await _seed_extraction_history(
        session_factory,
        department_id=department_id,
        requester=reviewer,
        suffix="071",
    )
    viewer_headers = _headers(viewer, token_service)
    guarded_paths = (
        f"/api/v1/document-files/{file_id}/extraction",
        f"/api/v1/extraction-runs/{current_run_id}",
        f"/api/v1/extraction-runs/{current_run_id}/containers",
    )

    file_states = (
        (DocumentFileStatus.AVAILABLE, False, None),
        (DocumentFileStatus.REPLACED, True, None),
        (DocumentFileStatus.DELETED, True, datetime.now(UTC)),
    )
    for status, is_current, deleted_at in file_states:
        async with session_factory() as session:
            document_file = await session.scalar(
                select(DocumentFile).where(DocumentFile.id == file_id)
            )
            assert document_file is not None
            document_file.file_status = status
            document_file.is_current = is_current
            document_file.deleted_at = deleted_at
            await session.commit()

        for path in guarded_paths:
            response = await api_client.get(path, headers=viewer_headers)
            assert response.status_code == 404

    reviewer_old_run = await api_client.get(
        f"/api/v1/extraction-runs/{old_run_id}",
        headers=_headers(reviewer, token_service),
    )
    assert reviewer_old_run.status_code == 200

    outside_scope = await api_client.get(
        f"/api/v1/extraction-runs/{old_run_id}",
        headers=_headers(outside_reviewer, token_service),
    )
    assert outside_scope.status_code == 404


@pytest.mark.asyncio
async def test_list_payloads_omit_unbounded_text_but_json_export_retains_it(
    api_client: AsyncClient,
    create_user,
    token_service: TokenService,
    session_factory,
) -> None:
    department_id = uuid4()
    controller = await create_user(
        email="controller.lightweight-content@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=department_id,
    )
    huge_text = "UNBOUNDED-CONTENT-MARKER " * 10_000
    _, _, run_id = await _seed_extraction_history(
        session_factory,
        department_id=department_id,
        requester=controller,
        suffix="072",
        raw_text=huge_text,
    )
    headers = _headers(controller, token_service)

    containers = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/containers",
        headers=headers,
    )
    assert containers.status_code == 200
    container_item = containers.json()["data"]["items"][0]
    assert "rawText" not in container_item
    assert "normalisedText" not in container_item
    assert "UNBOUNDED-CONTENT-MARKER" not in containers.text

    tables = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/tables",
        headers=headers,
    )
    assert tables.status_code == 200
    assert "rawText" not in tables.json()["data"]["items"][0]
    assert "UNBOUNDED-CONTENT-MARKER" not in tables.text

    exported = await api_client.get(
        f"/api/v1/extraction-runs/{run_id}/export",
        headers=headers,
        params={"format": "json"},
    )
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["containers"][0]["rawText"] == huge_text
    assert payload["containers"][0]["normalisedText"] == huge_text
    assert payload["tables"][0]["rawText"] == huge_text


def test_search_snippet_uses_valid_unicode_ellipsis() -> None:
    text = f"{'a' * 150}needle{'b' * 150}"
    snippet = _plain_text_snippet(text, "needle")

    assert snippet.startswith("\N{HORIZONTAL ELLIPSIS}")
    assert snippet.endswith("\N{HORIZONTAL ELLIPSIS}")
    assert snippet.count("\N{HORIZONTAL ELLIPSIS}") == 2
