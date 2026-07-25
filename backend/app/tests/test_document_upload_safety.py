"""Transaction, expiry, tamper, scope, and privacy tests for uploads."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.main import app
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.upload_session import UploadSession, UploadSessionStatus
from app.models.upload_session_item import UploadSessionItem
from app.models.user import User
from app.repositories.document_file_repository import DocumentFileRepository
from app.schemas.document_upload import (
    UploadConfirmationItem,
    UploadConfirmationRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.auth.token_service import TokenService
from app.services.documents.document_upload_service import (
    DocumentUploadService,
)
from app.services.documents.upload_cleanup_service import (
    UploadCleanupService,
)
from app.services.storage.local_storage import LocalStorage
from app.tests.conftest import TestSessionFactory, UserFactory
from app.tests.test_document_files_api import (
    PDF_MIME,
    _confirm_attach,
    _create_register_document,
    _pdf,
    _preview_pdf,
    _settings,
)
from app.tests.test_documents_api import _headers, _seed_master
from app.utils.datetime import utc_now


class FailOnceDeleteStorage(LocalStorage):
    """Local storage fault used to prove terminal cleanup retryability."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.delete_failures = 1

    async def delete(self, storage_key: str) -> None:
        if self.delete_failures:
            self.delete_failures -= 1
            raise OSError("forced temporary cleanup failure")
        await super().delete(storage_key)


def test_confirmation_schema_supports_configurable_batches_above_fifty(
) -> None:
    payload = UploadConfirmationRequest(
        items=[
            UploadConfirmationItem(
                upload_item_id=uuid4(),
                action="SKIP",
            )
            for _ in range(51)
        ]
    )
    assert len(payload.items) == 51


@pytest.mark.asyncio
async def test_revision_without_document_is_rejected_before_staging(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="revision-without-document",
    )
    _, revision_id = await _create_register_document(
        api_client,
        headers,
        master,
    )

    response = await api_client.post(
        "/api/v1/document-files/upload",
        headers=headers,
        data={"revisionId": revision_id},
        files={
            "file": (
                "unidentified.pdf",
                _pdf("must not be staged"),
                PDF_MIME,
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["errors"][0] == {
        "field": "documentId",
        "message": "documentId is required when revisionId is provided.",
    }
    assert not any(
        path.is_file()
        for path in Path(settings.storage_root).rglob("*")
    )
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count(UploadSession.id)))
            == 0
        )


@pytest.mark.asyncio
async def test_expired_and_tampered_session_are_rejected_and_cleaned(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="expiry-tamper",
    )
    document_id, revision_id = await _create_register_document(
        api_client,
        headers,
        master,
    )
    expired_preview = await _preview_pdf(
        api_client,
        headers,
        document_id=document_id,
        revision_id=revision_id,
    )
    expired_session_id = UUID(expired_preview["sessionId"])
    async with session_factory() as session:
        upload_session = await session.get(UploadSession, expired_session_id)
        assert upload_session is not None
        upload_session.expires_at = utc_now() - timedelta(minutes=1)
        item = await session.scalar(
            select(UploadSessionItem).where(
                UploadSessionItem.upload_session_id == expired_session_id
            )
        )
        assert item is not None
        expired_key = item.temporary_storage_key
        await session.commit()
    expired = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{expired_preview['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        expired_preview["items"][0]["uploadItemId"]
                    ),
                    "action": "ATTACH_TO_EXISTING_REVISION",
                    "documentId": document_id,
                    "revisionId": revision_id,
                }
            ]
        },
    )
    assert expired.status_code == 409
    storage = LocalStorage(settings.storage_root)
    assert not await storage.exists(expired_key)
    async with session_factory() as session:
        state = await session.get(UploadSession, expired_session_id)
        assert state is not None
        assert state.status == UploadSessionStatus.EXPIRED

    tampered_preview = await _preview_pdf(
        api_client,
        headers,
        content=_pdf("before-tamper"),
        document_id=document_id,
        revision_id=revision_id,
    )
    tampered_session_id = UUID(tampered_preview["sessionId"])
    async with session_factory() as session:
        item = await session.scalar(
            select(UploadSessionItem).where(
                UploadSessionItem.upload_session_id == tampered_session_id
            )
        )
        assert item is not None
        tampered_key = item.temporary_storage_key
    await storage.delete(tampered_key)
    await storage.save(BytesIO(_pdf("changed-after-preview")), tampered_key)
    tampered = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{tampered_preview['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        tampered_preview["items"][0]["uploadItemId"]
                    ),
                    "action": "ATTACH_TO_EXISTING_REVISION",
                    "documentId": document_id,
                    "revisionId": revision_id,
                }
            ]
        },
    )
    assert tampered.status_code == 409
    assert "changed after preview" in tampered.text
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count(DocumentFile.id)))
            == 0
        )


@pytest.mark.parametrize(
    ("terminal_action", "expected_status"),
    (
        ("cancel", UploadSessionStatus.CANCELLED),
        ("expire", UploadSessionStatus.EXPIRED),
    ),
)
@pytest.mark.asyncio
async def test_terminal_cleanup_failure_is_retried(
    terminal_action: str,
    expected_status: UploadSessionStatus,
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    suffix = f"cleanup-retry-{terminal_action}"
    headers = await _headers(
        create_user,
        token_service,
        suffix=suffix,
    )
    preview = await _preview_pdf(
        api_client,
        headers,
        filename="unidentified.pdf",
        content=_pdf(f"cleanup retry {terminal_action}"),
    )
    session_id = UUID(preview["sessionId"])
    item_id = UUID(preview["items"][0]["uploadItemId"])
    storage = FailOnceDeleteStorage(settings.storage_root)

    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(
                User.email
                == f"documents-{suffix}@example.com"
            )
        )
        upload_session = await session.get(UploadSession, session_id)
        assert user is not None
        assert upload_session is not None
        if terminal_action == "expire":
            upload_session.expires_at = utc_now() - timedelta(minutes=1)
            await session.commit()

        service = DocumentUploadService(
            session,
            settings,
            user,
            RequestMetadata(ip_address=None, user_agent=None),
            storage=storage,
        )
        if terminal_action == "cancel":
            cancelled = await service.cancel(session_id)
            assert cancelled.status == UploadSessionStatus.CANCELLED
        else:
            with pytest.raises(ApplicationError) as caught:
                await service.confirm(
                    session_id,
                    UploadConfirmationRequest(
                        items=[
                            UploadConfirmationItem(
                                upload_item_id=item_id,
                                action="SKIP",
                            )
                        ]
                    ),
                )
            assert caught.value.errors
            assert "expired" in caught.value.errors[0].message

        terminal = await session.get(UploadSession, session_id)
        item = await session.get(UploadSessionItem, item_id)
        assert terminal is not None
        assert item is not None
        assert terminal.status == expected_status
        assert item.temporary_cleanup_pending is True
        assert await storage.exists(item.temporary_storage_key)

        summary = await UploadCleanupService(
            session,
            storage=storage,
        ).cleanup_expired(now=utc_now())
        assert summary.scanned_sessions == 1
        assert summary.deleted_files == 1
        assert summary.failed_sessions == 0
        await session.refresh(item)
        assert item.temporary_cleanup_pending is False
        assert not await storage.exists(item.temporary_storage_key)

        repeated = await UploadCleanupService(
            session,
            storage=storage,
        ).cleanup_expired(now=utc_now())
        assert repeated.scanned_sessions == 0


@pytest.mark.parametrize("preview_mode", ("single", "batch"))
@pytest.mark.asyncio
async def test_preview_commit_failure_removes_uncommitted_storage(
    preview_mode: str,
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    headers = await _headers(
        create_user,
        token_service,
        suffix=f"preview-compensation-{preview_mode}",
    )

    async def fail_commit(_: AsyncSession) -> None:
        raise RuntimeError("forced preview commit failure")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced preview commit"):
        if preview_mode == "single":
            await api_client.post(
                "/api/v1/document-files/upload",
                headers=headers,
                files={
                    "file": (
                        "unidentified.pdf",
                        _pdf("single preview compensation"),
                        PDF_MIME,
                    )
                },
            )
        else:
            await api_client.post(
                "/api/v1/document-files/batch-upload",
                headers=headers,
                files=[
                    (
                        "files",
                        (
                            "first.pdf",
                            _pdf("batch compensation one"),
                            PDF_MIME,
                        ),
                    ),
                    (
                        "files",
                        (
                            "second.pdf",
                            _pdf("batch compensation two"),
                            PDF_MIME,
                        ),
                    ),
                ],
            )

    stored_files = await asyncio.to_thread(
        lambda: [
            path
            for path in Path(settings.storage_root).rglob("*")
            if path.is_file()
        ]
    )
    assert stored_files == []
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count(UploadSession.id)))
            == 0
        )
        assert (
            await session.scalar(
                select(func.count(UploadSessionItem.id))
            )
            == 0
        )


@pytest.mark.asyncio
async def test_database_failure_rolls_back_register_and_removes_final_file(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="compensation",
    )
    preview = await _preview_pdf(
        api_client,
        headers,
        filename="MTI-HRM-IER-SOP-777_Rev.000.pdf",
        content=_pdf("compensation"),
    )

    async def fail_create(
        _: DocumentFileRepository,
        __: DocumentFile,
    ) -> DocumentFile:
        raise IntegrityError(
            "forced document_files insert",
            {},
            RuntimeError("forced failure"),
        )

    monkeypatch.setattr(DocumentFileRepository, "create", fail_create)
    response = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{preview['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": preview["items"][0]["uploadItemId"],
                    "action": "CREATE_DOCUMENT_AND_REVISION",
                    "metadata": {
                        "companyCode": "MTI",
                        "departmentId": str(master["department"].id),
                        "sectionId": str(master["section"].id),
                        "documentTypeId": str(master["document_type"].id),
                        "documentNumber": "777",
                        "title": "Must roll back",
                        "revisionCode": "Rev.000",
                    },
                }
            ]
        },
    )
    assert response.status_code == 409, response.text
    async with session_factory() as session:
        assert await session.scalar(select(func.count(Document.id))) == 0
        assert (
            await session.scalar(select(func.count(DocumentFile.id)))
            == 0
        )
        upload_session = await session.get(
            UploadSession,
            UUID(preview["sessionId"]),
        )
        assert upload_session is not None
        assert upload_session.status == UploadSessionStatus.FAILED
    root = Path(settings.storage_root)
    stored_files = await asyncio.to_thread(
        lambda: [path for path in root.rglob("*") if path.is_file()]
    )
    assert stored_files == []


@pytest.mark.asyncio
async def test_duplicate_privacy_permissions_and_department_scope(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    master = await _seed_master(session_factory)
    admin_headers = await _headers(
        create_user,
        token_service,
        suffix="privacy-admin",
    )
    document_id, revision_id = await _create_register_document(
        api_client,
        admin_headers,
        master,
    )
    preview = await _preview_pdf(
        api_client,
        admin_headers,
        document_id=document_id,
        revision_id=revision_id,
    )
    confirmed = await _confirm_attach(
        api_client,
        admin_headers,
        preview,
        document_id,
        revision_id,
    )
    file_id = confirmed["items"][0]["documentFileId"]

    department_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.DEPARTMENT_USER,
        department_id=master["other_department"].id,
        suffix="privacy-department",
    )
    duplicate = await _preview_pdf(
        api_client,
        department_headers,
        filename="unidentified.pdf",
    )
    item = duplicate["items"][0]
    assert item["identificationStatus"] == "DUPLICATE_FILE"
    assert item["duplicateWarning"]["message"] == (
        "Duplicate file already exists."
    )
    assert item["duplicateWarning"]["documentId"] is None
    assert item["duplicateWarning"]["revisionId"] is None
    assert item["duplicateWarning"]["baseDocumentCode"] is None

    metadata = await api_client.get(
        f"/api/v1/document-files/{file_id}",
        headers=department_headers,
    )
    download = await api_client.get(
        f"/api/v1/document-files/{file_id}/download",
        headers=department_headers,
    )
    scoped_history = await api_client.get(
        "/api/v1/document-files/history",
        headers=department_headers,
        params={"departmentId": str(master["department"].id)},
    )
    assert metadata.status_code == 403
    assert download.status_code == 403
    assert scoped_history.status_code == 403

    viewer_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.VIEWER,
        department_id=master["other_department"].id,
        suffix="privacy-viewer",
    )
    upload_denied = await api_client.post(
        "/api/v1/document-files/upload",
        headers=viewer_headers,
        files={
            "file": (
                "unidentified.pdf",
                _pdf("viewer"),
                PDF_MIME,
            )
        },
    )
    history_denied = await api_client.get(
        "/api/v1/document-files/history",
        headers=viewer_headers,
    )
    assert upload_denied.status_code == 403
    assert history_denied.status_code == 403

    reviewer_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.REVIEWER,
        department_id=None,
        suffix="privacy-reviewer-no-department",
    )
    reviewer_history = await api_client.get(
        "/api/v1/document-files/history",
        headers=reviewer_headers,
    )
    assert reviewer_history.status_code == 200
    assert reviewer_history.json()["data"]["totalItems"] == 0

    duplicate_check_disabled = settings.model_copy(
        update={"enable_duplicate_file_hash_check": False}
    )
    app.dependency_overrides[get_settings] = (
        lambda: duplicate_check_disabled
    )
    disabled_preview = await _preview_pdf(
        api_client,
        department_headers,
        filename="unidentified-duplicate-check-disabled.pdf",
    )
    assert (
        disabled_preview["items"][0]["identificationStatus"]
        != "DUPLICATE_FILE"
    )
    assert disabled_preview["items"][0]["duplicateWarning"] is None
