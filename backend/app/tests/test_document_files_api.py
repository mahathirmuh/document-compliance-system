"""Phase 5 physical-file API integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.authorization import AuditAction, UserRole
from app.core.config import Settings, get_settings
from app.main import app
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.upload_session import UploadSession, UploadSessionStatus
from app.models.upload_session_item import UploadSessionItem
from app.services.auth.token_service import TokenService
from app.tests.conftest import (
    TestSessionFactory,
    UserFactory,
)
from app.tests.test_documents_api import (
    _create_payload,
    _headers,
    _seed_master,
)

PDF_MIME = "application/pdf"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)
XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument."
    "spreadsheetml.sheet"
)


def _settings(tmp_path: Path) -> Settings:
    settings = get_settings().model_copy(
        update={"storage_root": tmp_path / "private-storage"}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    return settings


def _pdf(marker: str = "original") -> bytes:
    return (
        f"%PDF-1.7\n% Phase 5 {marker}\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    ).encode()


def _ooxml(kind: str) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            "<Types xmlns='http://schemas.openxmlformats.org/package/"
            "2006/content-types'/>",
        )
        archive.writestr(
            "word/document.xml"
            if kind == "docx"
            else "xl/workbook.xml",
            "<root/>",
        )
    return stream.getvalue()


async def _create_register_document(
    api_client: AsyncClient,
    headers: dict[str, str],
    master: dict[str, Any],
) -> tuple[str, str]:
    response = await api_client.post(
        "/api/v1/documents",
        headers=headers,
        json=_create_payload(master),
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    return data["id"], data["currentRevision"]["id"]


async def _preview_pdf(
    api_client: AsyncClient,
    headers: dict[str, str],
    *,
    filename: str = "MTI-HRM-IER-SOP-001_Rev.000.pdf",
    content: bytes | None = None,
    document_id: str | None = None,
    revision_id: str | None = None,
) -> dict[str, Any]:
    form: dict[str, str] = {}
    if document_id is not None:
        form["documentId"] = document_id
    if revision_id is not None:
        form["revisionId"] = revision_id
    response = await api_client.post(
        "/api/v1/document-files/upload",
        headers=headers,
        data=form,
        files={
            "file": (
                filename,
                content or _pdf(),
                PDF_MIME,
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _confirm_attach(
    api_client: AsyncClient,
    headers: dict[str, str],
    preview: dict[str, Any],
    document_id: str,
    revision_id: str,
) -> dict[str, Any]:
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
                    "action": "ATTACH_TO_EXISTING_REVISION",
                    "documentId": document_id,
                    "revisionId": revision_id,
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_supported_formats_and_invalid_file_rejection(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    headers = await _headers(
        create_user,
        token_service,
        suffix="file-formats",
    )
    formats = (
        ("unidentified.pdf", _pdf(), PDF_MIME, "pdf"),
        ("unidentified.docx", _ooxml("docx"), DOCX_MIME, "docx"),
        ("unidentified.xlsx", _ooxml("xlsx"), XLSX_MIME, "xlsx"),
    )
    for filename, content, mime, extension in formats:
        response = await api_client.post(
            "/api/v1/document-files/upload",
            headers=headers,
            files={"file": (filename, content, mime)},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["status"] == "READY_FOR_CONFIRMATION"
        assert data["items"][0]["fileExtension"] == extension
        assert len(data["items"][0]["sha256Hash"]) == 64
        cancelled = await api_client.post(
            (
                "/api/v1/document-files/upload/"
                f"{data['sessionId']}/cancel"
            ),
            headers=headers,
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["data"]["status"] == "CANCELLED"

    cases = (
        ("unsupported.pptx", _ooxml("docx"), DOCX_MIME, 415),
        ("photo.jpg", b"\xff\xd8\xff\xe0", "image/jpeg", 415),
        ("fake.pdf", b"not-a-pdf", PDF_MIME, 415),
        ("mismatch.pdf", _ooxml("xlsx"), PDF_MIME, 415),
        ("../../secret.pdf", _pdf(), PDF_MIME, 422),
    )
    for filename, content, mime, expected in cases:
        response = await api_client.post(
            "/api/v1/document-files/upload",
            headers=headers,
            files={"file": (filename, content, mime)},
        )
        assert response.status_code == expected, response.text
        assert response.json()["success"] is False
        if filename in {"unsupported.pptx", "photo.jpg"}:
            assert not any(
                path.is_file()
                for path in Path(settings.storage_root).rglob("*")
            )


@pytest.mark.asyncio
async def test_existing_revision_download_replace_delete_restore_and_history(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    _settings(tmp_path)
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="file-lifecycle",
    )
    document_id, revision_id = await _create_register_document(
        api_client,
        headers,
        master,
    )
    preview = await _preview_pdf(
        api_client,
        headers,
        document_id=document_id,
        revision_id=revision_id,
    )
    assert preview["items"][0]["identificationStatus"] == "IDENTIFIED"
    assert (
        preview["items"][0]["proposedAction"]
        == "ATTACH_TO_EXISTING_REVISION"
    )
    confirmed = await _confirm_attach(
        api_client,
        headers,
        preview,
        document_id,
        revision_id,
    )
    file_id = confirmed["items"][0]["documentFileId"]

    metadata = await api_client.get(
        f"/api/v1/document-files/{file_id}",
        headers=headers,
    )
    assert metadata.status_code == 200, metadata.text
    assert "storageKey" not in metadata.text
    assert metadata.json()["data"]["isCurrent"] is True

    downloaded = await api_client.get(
        f"/api/v1/document-files/{file_id}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == _pdf()
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert "attachment;" in downloaded.headers["content-disposition"]

    duplicate = await _preview_pdf(
        api_client,
        headers,
        document_id=document_id,
        revision_id=revision_id,
    )
    assert duplicate["items"][0]["identificationStatus"] == "DUPLICATE_FILE"
    assert duplicate["items"][0]["proposedAction"] == "SKIP"
    repeated = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{preview['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": preview["items"][0]["uploadItemId"],
                    "action": "ATTACH_TO_EXISTING_REVISION",
                    "documentId": document_id,
                    "revisionId": revision_id,
                }
            ]
        },
    )
    assert repeated.status_code == 409

    stale_replacement = await _preview_pdf(
        api_client,
        headers,
        content=_pdf("stale replacement"),
        document_id=document_id,
        revision_id=revision_id,
    )
    assert (
        stale_replacement["items"][0]["proposedAction"]
        == "REPLACE_CURRENT_FILE"
    )
    replacement_bytes = _pdf("replacement")
    replaced = await api_client.post(
        f"/api/v1/document-files/{file_id}/replace",
        headers=headers,
        data={"reason": "Controlled replacement"},
        files={
            "file": (
                "MTI-HRM-IER-SOP-001_Rev.000.pdf",
                replacement_bytes,
                PDF_MIME,
            )
        },
    )
    assert replaced.status_code == 200, replaced.text
    replacement_id = replaced.json()["data"]["id"]
    assert replacement_id != file_id

    stale_confirm = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{stale_replacement['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        stale_replacement["items"][0]["uploadItemId"]
                    ),
                    "action": "REPLACE_CURRENT_FILE",
                    "documentId": document_id,
                    "revisionId": revision_id,
                    "metadata": {"reason": "Stale operator view"},
                }
            ]
        },
    )
    assert stale_confirm.status_code == 409
    assert "current file changed" in stale_confirm.text

    old = await api_client.get(
        f"/api/v1/document-files/{file_id}",
        headers=headers,
    )
    assert old.json()["data"]["fileStatus"] == "REPLACED"
    assert old.json()["data"]["replacedByFileId"] == replacement_id

    deleted = await api_client.post(
        f"/api/v1/document-files/{replacement_id}/delete",
        headers=headers,
        json={"reason": "Incorrect replacement"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["fileStatus"] == "DELETED"
    assert "preDeleteStorageKey" not in deleted.text
    assert "storageKey" not in deleted.text
    blocked_download = await api_client.get(
        f"/api/v1/document-files/{replacement_id}/download",
        headers=headers,
    )
    assert blocked_download.status_code == 409

    restored = await api_client.post(
        f"/api/v1/document-files/{replacement_id}/restore",
        headers=headers,
        json={"reason": "Validated", "replaceCurrent": False},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["fileStatus"] == "AVAILABLE"
    assert restored.json()["data"]["isCurrent"] is True
    restored_download = await api_client.get(
        (
            f"/api/v1/documents/{document_id}/revisions/"
            f"{revision_id}/download"
        ),
        headers=headers,
    )
    assert restored_download.status_code == 200
    assert restored_download.content == replacement_bytes

    deleted_old = await api_client.post(
        f"/api/v1/document-files/{file_id}/delete",
        headers=headers,
        json={"reason": "Restore historical source"},
    )
    assert deleted_old.status_code == 200, deleted_old.text
    restored_old = await api_client.post(
        f"/api/v1/document-files/{file_id}/restore",
        headers=headers,
        json={
            "reason": "Explicit rollback",
            "replaceCurrent": True,
        },
    )
    assert restored_old.status_code == 200, restored_old.text
    restored_old_data = restored_old.json()["data"]
    assert restored_old_data["isCurrent"] is True
    assert restored_old_data["replacedAt"] is None
    assert restored_old_data["replacedByFileId"] is None
    replacement_history = await api_client.get(
        f"/api/v1/document-files/{replacement_id}",
        headers=headers,
    )
    assert replacement_history.json()["data"]["fileStatus"] == "REPLACED"
    assert (
        replacement_history.json()["data"]["replacedByFileId"]
        == file_id
    )

    history = await api_client.get(
        "/api/v1/document-files/history",
        headers=headers,
        params={"documentId": document_id},
    )
    assert history.status_code == 200, history.text
    assert history.json()["data"]["totalItems"] == 2
    statuses = {
        item["fileStatus"] for item in history.json()["data"]["items"]
    }
    assert statuses == {"AVAILABLE", "REPLACED"}

    async with session_factory() as session:
        current_count = await session.scalar(
                select(func.count(DocumentFile.id)).where(
                    DocumentFile.document_revision_id
                    == UUID(revision_id),
                DocumentFile.is_current.is_(True),
                DocumentFile.is_primary.is_(True),
            )
        )
        assert current_count == 1
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(
                        AuditLog.action.in_(
                            (
                                AuditAction.CONFIRM_FILE_UPLOAD,
                                AuditAction.REPLACE_DOCUMENT_FILE,
                                AuditAction.DELETE_DOCUMENT_FILE,
                                AuditAction.RESTORE_DOCUMENT_FILE,
                                AuditAction.DOWNLOAD_DOCUMENT_FILE,
                            )
                        )
                    )
                )
            ).all()
        )
        assert {
            AuditAction.CONFIRM_FILE_UPLOAD,
            AuditAction.REPLACE_DOCUMENT_FILE,
            AuditAction.DELETE_DOCUMENT_FILE,
            AuditAction.RESTORE_DOCUMENT_FILE,
            AuditAction.DOWNLOAD_DOCUMENT_FILE,
        }.issubset(actions)
        delete_audits = list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.action
                        == AuditAction.DELETE_DOCUMENT_FILE
                    )
                )
            ).all()
        )
        old_states = {
            (
                audit.old_values_json["fileStatus"],
                audit.old_values_json["isCurrent"],
            )
            for audit in delete_audits
            if audit.old_values_json is not None
        }
        assert ("AVAILABLE", True) in old_states
        assert ("REPLACED", False) in old_states
        replace_audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.action == AuditAction.REPLACE_DOCUMENT_FILE
            )
        )
        assert replace_audit is not None
        assert replace_audit.old_values_json is not None
        assert replace_audit.old_values_json["fileStatus"] == "AVAILABLE"
        assert replace_audit.old_values_json["isCurrent"] is True


@pytest.mark.asyncio
async def test_archived_file_policy_and_manual_replacement(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    _settings(tmp_path)
    master = await _seed_master(session_factory)
    admin_headers = await _headers(
        create_user,
        token_service,
        suffix="archived-files-admin",
    )
    document_id, revision_id = await _create_register_document(
        api_client,
        admin_headers,
        master,
    )
    archived = await api_client.post(
        f"/api/v1/documents/{document_id}/archive",
        headers=admin_headers,
        json={"reason": "Controlled archive"},
    )
    assert archived.status_code == 200, archived.text

    department_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.DEPARTMENT_USER,
        department_id=master["department"].id,
        suffix="archived-files-department",
    )
    blocked_preview = await api_client.post(
        "/api/v1/document-files/upload",
        headers=department_headers,
        data={
            "documentId": document_id,
            "revisionId": revision_id,
        },
        files={
            "file": (
                "unidentified.pdf",
                _pdf("blocked before staging"),
                PDF_MIME,
            )
        },
    )
    assert blocked_preview.status_code == 400
    assert "Archived documents" in blocked_preview.text
    async with session_factory() as session:
        assert (
            await session.scalar(select(func.count(UploadSession.id)))
            == 0
        )

    admin_preview = await _preview_pdf(
        api_client,
        admin_headers,
        filename="unidentified.pdf",
        content=_pdf("archived attach exception"),
        document_id=document_id,
        revision_id=revision_id,
    )
    attached = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{admin_preview['sessionId']}/confirm"
        ),
        headers=admin_headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        admin_preview["items"][0]["uploadItemId"]
                    ),
                    "action": "ATTACH_TO_EXISTING_REVISION",
                    "documentId": document_id,
                    "revisionId": revision_id,
                    "metadata": {
                        "reason": "Super Admin archive exception"
                    },
                }
            ]
        },
    )
    assert attached.status_code == 200, attached.text
    file_id = attached.json()["data"]["items"][0]["documentFileId"]

    blocked_replace = await api_client.post(
        f"/api/v1/document-files/{file_id}/replace",
        headers=admin_headers,
        data={"reason": "Must remain read-only"},
        files={
            "file": (
                "unidentified.pdf",
                _pdf("blocked archived replacement"),
                PDF_MIME,
            )
        },
    )
    blocked_delete = await api_client.post(
        f"/api/v1/document-files/{file_id}/delete",
        headers=admin_headers,
        json={"reason": "Must remain read-only"},
    )
    assert blocked_replace.status_code == 409
    assert blocked_delete.status_code == 409

    unarchived = await api_client.post(
        f"/api/v1/documents/{document_id}/restore",
        headers=admin_headers,
        json={},
    )
    assert unarchived.status_code == 200, unarchived.text
    manual_preview = await _preview_pdf(
        api_client,
        admin_headers,
        filename="unidentified.pdf",
        content=_pdf("manual replacement"),
    )
    assert (
        manual_preview["items"][0]["proposedAction"]
        == "MANUAL_REVIEW"
    )
    manual_replaced = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{manual_preview['sessionId']}/confirm"
        ),
        headers=admin_headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        manual_preview["items"][0]["uploadItemId"]
                    ),
                    "action": "REPLACE_CURRENT_FILE",
                    "documentId": document_id,
                    "revisionId": revision_id,
                    "metadata": {"reason": "Manually selected target"},
                }
            ]
        },
    )
    assert manual_replaced.status_code == 200, manual_replaced.text
    replacement_id = manual_replaced.json()["data"]["items"][0][
        "documentFileId"
    ]

    deleted = await api_client.post(
        f"/api/v1/document-files/{file_id}/delete",
        headers=admin_headers,
        json={"reason": "Prepare archived restore guard"},
    )
    assert deleted.status_code == 200, deleted.text
    archived_again = await api_client.post(
        f"/api/v1/documents/{document_id}/archive",
        headers=admin_headers,
        json={"reason": "Archive after replacement"},
    )
    assert archived_again.status_code == 200, archived_again.text
    blocked_restore = await api_client.post(
        f"/api/v1/document-files/{file_id}/restore",
        headers=admin_headers,
        json={"reason": "Must remain read-only", "replaceCurrent": True},
    )
    assert blocked_restore.status_code == 409
    current = await api_client.get(
        f"/api/v1/document-files/{replacement_id}",
        headers=admin_headers,
    )
    assert current.status_code == 200
    assert current.json()["data"]["isCurrent"] is True


@pytest.mark.asyncio
async def test_history_date_filters_use_application_timezone_day_bounds(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    _settings(tmp_path)
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="history-date-bounds",
    )
    document_id, revision_id = await _create_register_document(
        api_client,
        headers,
        master,
    )
    preview = await _preview_pdf(
        api_client,
        headers,
        document_id=document_id,
        revision_id=revision_id,
    )
    confirmed = await _confirm_attach(
        api_client,
        headers,
        preview,
        document_id,
        revision_id,
    )
    file_id = UUID(confirmed["items"][0]["documentFileId"])
    async with session_factory() as session:
        document_file = await session.get(DocumentFile, file_id)
        assert document_file is not None
        # 00:30 on 25 July in Asia/Makassar (UTC+8).
        document_file.uploaded_at = datetime(
            2026,
            7,
            24,
            16,
            30,
            tzinfo=UTC,
        )
        await session.commit()

    same_local_day = await api_client.get(
        "/api/v1/document-files/history",
        headers=headers,
        params={
            "uploadedFrom": "2026-07-25",
            "uploadedTo": "2026-07-25",
        },
    )
    prior_local_day = await api_client.get(
        "/api/v1/document-files/history",
        headers=headers,
        params={"uploadedTo": "2026-07-24"},
    )
    next_local_day = await api_client.get(
        "/api/v1/document-files/history",
        headers=headers,
        params={"uploadedFrom": "2026-07-26"},
    )
    assert same_local_day.status_code == 200, same_local_day.text
    assert same_local_day.json()["data"]["totalItems"] == 1
    assert prior_local_day.json()["data"]["totalItems"] == 0
    assert next_local_day.json()["data"]["totalItems"] == 0


@pytest.mark.asyncio
async def test_create_document_and_add_revision_from_upload(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    _settings(tmp_path)
    master = await _seed_master(session_factory)
    headers = await _headers(
        create_user,
        token_service,
        suffix="create-from-file",
    )
    preview = await _preview_pdf(
        api_client,
        headers,
        filename="MTI-HRM-IER-SOP-900_Rev.000.pdf",
    )
    item = preview["items"][0]
    assert item["proposedAction"] == "CREATE_DOCUMENT_AND_REVISION"
    created = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{preview['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": item["uploadItemId"],
                    "action": "CREATE_DOCUMENT_AND_REVISION",
                    "metadata": {
                        "companyCode": "MTI",
                        "departmentId": str(master["department"].id),
                        "sectionId": str(master["section"].id),
                        "documentTypeId": str(master["document_type"].id),
                        "documentNumber": "900",
                        "title": "Created from physical file",
                        "revisionCode": "Rev.000",
                        "documentStatusId": str(master["initial"].id),
                    },
                }
            ]
        },
    )
    assert created.status_code == 200, created.text
    created_item = created.json()["data"]["items"][0]
    document_id = created_item["documentId"]
    assert created_item["baseDocumentCode"] == "MTI-HRM-IER-SOP-900"

    next_preview = await _preview_pdf(
        api_client,
        headers,
        filename="MTI-HRM-IER-SOP-900_Rev.001.pdf",
        content=_pdf("revision-one"),
    )
    assert next_preview["items"][0]["proposedAction"] == "ADD_NEW_REVISION"
    added = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{next_preview['sessionId']}/confirm"
        ),
        headers=headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        next_preview["items"][0]["uploadItemId"]
                    ),
                    "action": "ADD_NEW_REVISION",
                    "documentId": document_id,
                    "metadata": {
                        "revisionCode": "Rev.001",
                        "documentStatusId": str(master["initial"].id),
                        "setAsCurrentRevision": True,
                    },
                }
            ]
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["data"]["items"][0]["revisionCode"] == "Rev.001"
    async with session_factory() as session:
        documents = int(
            await session.scalar(select(func.count(Document.id))) or 0
        )
        revisions = int(
            await session.scalar(select(func.count(DocumentRevision.id)))
            or 0
        )
        files = int(
            await session.scalar(select(func.count(DocumentFile.id))) or 0
        )
        assert (documents, revisions, files) == (1, 2, 2)


@pytest.mark.asyncio
async def test_batch_partial_commit_owner_and_department_scope(
    api_client: AsyncClient,
    create_user: UserFactory,
    token_service: TokenService,
    session_factory: TestSessionFactory,
    tmp_path: Path,
) -> None:
    _settings(tmp_path)
    master = await _seed_master(session_factory)
    owner_headers = await _headers(
        create_user,
        token_service,
        suffix="batch-owner",
    )
    document_id, revision_id = await _create_register_document(
        api_client,
        owner_headers,
        master,
    )
    batch = await api_client.post(
        "/api/v1/document-files/batch-upload",
        headers=owner_headers,
        files=[
            (
                "files",
                (
                    "MTI-HRM-IER-SOP-001_Rev.000.pdf",
                    _pdf("batch-valid"),
                    PDF_MIME,
                ),
            ),
            ("files", ("bad.pdf", b"not-a-pdf", PDF_MIME)),
        ],
    )
    assert batch.status_code == 201, batch.text
    data = batch.json()["data"]
    assert data["totalFiles"] == 2
    valid_item = next(
        item for item in data["items"] if item["status"] == "READY"
    )
    invalid_item = next(
        item for item in data["items"] if item["status"] == "FAILED"
    )
    assert invalid_item["quarantineReason"]
    assert invalid_item["quarantineReason"] in invalid_item["errors"]
    confirmed = await api_client.post(
        (
            "/api/v1/document-files/batch-upload/"
            f"{data['sessionId']}/confirm"
        ),
        headers=owner_headers,
        json={
            "items": [
                {
                    "uploadItemId": valid_item["uploadItemId"],
                    "action": "ATTACH_TO_EXISTING_REVISION",
                    "documentId": document_id,
                    "revisionId": revision_id,
                },
                {
                    "uploadItemId": invalid_item["uploadItemId"],
                    "action": "SKIP",
                },
            ]
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()["data"]
    assert result["committed"] == 1
    assert result["skipped"] == 1
    assert result["failed"] == 0
    assert result["filesAttached"] == 1

    second_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.DEPARTMENT_USER,
        department_id=master["other_department"].id,
        suffix="other-department",
    )
    outside = await api_client.post(
        "/api/v1/document-files/upload",
        headers=second_headers,
        data={"documentId": document_id, "revisionId": revision_id},
        files={
            "file": (
                "MTI-HRM-IER-SOP-001_Rev.000.pdf",
                _pdf("outside"),
                PDF_MIME,
            )
        },
    )
    assert outside.status_code == 403

    owned_preview = await _preview_pdf(
        api_client,
        owner_headers,
        filename="unidentified.pdf",
        content=_pdf("private-session"),
    )
    foreign_confirm = await api_client.post(
        (
            "/api/v1/document-files/upload/"
            f"{owned_preview['sessionId']}/confirm"
        ),
        headers=second_headers,
        json={
            "items": [
                {
                    "uploadItemId": (
                        owned_preview["items"][0]["uploadItemId"]
                    ),
                    "action": "SKIP",
                }
            ]
        },
    )
    assert foreign_confirm.status_code == 404
    async with session_factory() as session:
        upload_session = await session.get(
            UploadSession,
            UUID(data["sessionId"]),
        )
        assert upload_session is not None
        assert upload_session.status == UploadSessionStatus.COMMITTED
        item_count = int(
            await session.scalar(
                select(func.count(UploadSessionItem.id)).where(
                    UploadSessionItem.upload_session_id
                    == upload_session.id
                )
            )
            or 0
        )
        assert item_count == 2
