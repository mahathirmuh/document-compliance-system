"""Model invariants, migration metadata, and expired-upload cleanup."""

from __future__ import annotations

import io
import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.database.base import Base
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_file import DocumentFile, DocumentFileStatus
from app.models.document_revision import DocumentRevision
from app.models.upload_session import (
    UploadSession,
    UploadSessionStatus,
    UploadSessionType,
)
from app.models.upload_session_item import (
    UploadIdentificationStatus,
    UploadProposedAction,
    UploadSessionItem,
    UploadSessionItemStatus,
)
from app.services.documents.upload_cleanup_service import (
    UploadCleanupService,
)
from app.services.storage.local_storage import LocalStorage


def test_phase5_model_metadata_contains_required_constraints_and_indexes() -> None:
    assert {
        "document_files",
        "upload_sessions",
        "upload_session_items",
    }.issubset(Base.metadata.tables)

    document_files = Base.metadata.tables["document_files"]
    assert {
        "id",
        "document_id",
        "document_revision_id",
        "original_filename",
        "sanitized_filename",
        "file_extension",
        "mime_type",
        "detected_mime_type",
        "file_size",
        "sha256_hash",
        "storage_provider",
        "storage_key",
        "storage_bucket",
        "file_status",
        "is_primary",
        "is_current",
        "uploaded_by",
        "uploaded_at",
        "replaced_at",
        "replaced_by_file_id",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
        "metadata_json",
        "created_at",
        "updated_at",
    } == set(document_files.c.keys())
    index_names = {index.name for index in document_files.indexes}
    assert "uq_document_files_one_current_primary" in index_names
    current_index = next(
        index
        for index in document_files.indexes
        if index.name == "uq_document_files_one_current_primary"
    )
    assert current_index.unique is True
    assert current_index.dialect_options["postgresql"]["where"] is not None
    assert current_index.dialect_options["sqlite"]["where"] is not None

    relationship_names = set(inspect(Document).relationships.keys())
    revision_relationships = set(
        inspect(DocumentRevision).relationships.keys()
    )
    assert "files" in relationship_names
    assert "files" in revision_relationships


def test_phase5_migration_has_linear_revision_and_exact_audit_actions() -> None:
    migration = runpy.run_path(
        str(
            Path(__file__).parents[2]
            / "alembic"
            / "versions"
            / "20260725_0004_phase5_physical_document_files.py"
        )
    )

    assert migration["revision"] == "20260725_0004"
    assert migration["down_revision"] == "20260725_0003"
    assert len(migration["PHASE5_AUDIT_ACTIONS"]) == 15
    assert migration["PHASE5_AUDIT_ACTIONS"][0] == "UPLOAD_FILE_PREVIEW"
    assert (
        migration["PHASE5_AUDIT_ACTIONS"][-1]
        == "CLEANUP_EXPIRED_UPLOAD_SESSION"
    )


@pytest.mark.asyncio
async def test_partial_unique_index_allows_only_one_current_primary_file(
    session_factory,
) -> None:
    document = Document(
        company_code="MTI",
        department_id=uuid4(),
        document_type_id=uuid4(),
        document_number="001",
        base_document_code="MTI-HRM-POL-001",
        title="Policy",
    )
    revision = DocumentRevision(
        document=document,
        revision_code="Rev.000",
        revision_number=0,
        full_document_code="MTI-HRM-POL-001_Rev.000",
        document_status_id=uuid4(),
        is_current=True,
    )
    first = DocumentFile(
        document=document,
        revision=revision,
        original_filename="Policy.pdf",
        sanitized_filename="Policy.pdf",
        file_extension="pdf",
        mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size=10,
        sha256_hash="a" * 64,
        storage_key="documents/originals/first.pdf",
        file_status=DocumentFileStatus.AVAILABLE,
        is_primary=True,
        is_current=True,
    )
    async with session_factory() as session:
        session.add_all([document, revision, first])
        await session.commit()
        second = DocumentFile(
            document=document,
            revision=revision,
            original_filename="Policy replacement.pdf",
            sanitized_filename="Policy_replacement.pdf",
            file_extension="pdf",
            mime_type="application/pdf",
            detected_mime_type="application/pdf",
            file_size=11,
            sha256_hash="b" * 64,
            storage_key="documents/originals/second.pdf",
            file_status=DocumentFileStatus.AVAILABLE,
            is_primary=True,
            is_current=True,
        )
        session.add(second)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_cleanup_expires_only_expired_sessions_and_is_idempotent(
    session_factory,
    create_user,
    tmp_path,
) -> None:
    user = await create_user()
    storage = LocalStorage(tmp_path)
    now = datetime.now(UTC)
    expired_key = "documents/temporary/expired/file.pdf"
    active_key = "documents/temporary/active/file.pdf"
    await storage.save(io.BytesIO(b"expired"), expired_key)
    await storage.save(io.BytesIO(b"active"), active_key)

    expired = UploadSession(
        user_id=user.id,
        session_type=UploadSessionType.SINGLE,
        status=UploadSessionStatus.READY_FOR_CONFIRMATION,
        total_files=1,
        total_size=7,
        expires_at=now - timedelta(minutes=1),
        items=[
            UploadSessionItem(
                temporary_storage_key=expired_key,
                original_filename="Expired.pdf",
                sanitized_filename="Expired.pdf",
                file_extension="pdf",
                mime_type="application/pdf",
                detected_mime_type="application/pdf",
                file_size=7,
                sha256_hash="a" * 64,
                identification_status=(
                    UploadIdentificationStatus.IDENTIFIED
                ),
                proposed_action=(
                    UploadProposedAction.ATTACH_TO_EXISTING_REVISION
                ),
                status=UploadSessionItemStatus.READY,
            )
        ],
    )
    active = UploadSession(
        user_id=user.id,
        session_type=UploadSessionType.SINGLE,
        status=UploadSessionStatus.READY_FOR_CONFIRMATION,
        total_files=1,
        total_size=6,
        expires_at=now + timedelta(hours=1),
        items=[
            UploadSessionItem(
                temporary_storage_key=active_key,
                original_filename="Active.pdf",
                sanitized_filename="Active.pdf",
                file_extension="pdf",
                mime_type="application/pdf",
                detected_mime_type="application/pdf",
                file_size=6,
                sha256_hash="b" * 64,
                identification_status=(
                    UploadIdentificationStatus.IDENTIFIED
                ),
                proposed_action=(
                    UploadProposedAction.ATTACH_TO_EXISTING_REVISION
                ),
                status=UploadSessionItemStatus.READY,
            )
        ],
    )

    async with session_factory() as session:
        session.add_all([expired, active])
        await session.commit()

        summary = await UploadCleanupService(
            session,
            storage=storage,
        ).cleanup_expired(now=now)
        assert summary.scanned_sessions == 1
        assert summary.expired_sessions == 1
        assert summary.deleted_files == 1
        assert summary.failed_sessions == 0
        assert expired.status == UploadSessionStatus.EXPIRED
        assert (
            expired.items[0].status
            == UploadSessionItemStatus.CANCELLED
        )
        assert active.status == UploadSessionStatus.READY_FOR_CONFIRMATION
        assert not await storage.exists(expired_key)
        assert await storage.exists(active_key)

        second = await UploadCleanupService(
            session,
            storage=storage,
        ).cleanup_expired(now=now)
        assert second.scanned_sessions == 0

        audit = await session.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == expired.id,
            )
        )
        assert audit is not None
        assert (
            audit.action.value
            == "CLEANUP_EXPIRED_UPLOAD_SESSION"
        )
