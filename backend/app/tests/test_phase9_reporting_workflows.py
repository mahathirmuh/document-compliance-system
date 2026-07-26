"""Operational Phase 9 advanced-report workflow coverage."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies.auth import get_token_service
from app.api.v1.endpoints.advanced_reports import router
from app.core.authorization import UserRole
from app.core.config import Settings, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.database.session import get_db_session
from app.models.department import Department
from app.models.report_schedule import ReportSchedule
from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)
from app.models.user import User
from app.schemas.advanced_reporting import AdvancedReportFilters
from app.services.auth.token_service import TokenService
from app.services.reporting.advanced_reporting_service import (
    AdvancedReportingService,
)
from app.services.reporting.report_dataset_service import (
    ReportDataset,
    ReportDatasetService,
)
from app.services.reporting.report_export_service import ReportExportService
from app.services.reporting.report_xlsx_service import ReportXlsxService
from app.services.reporting.reporting_worker_service import (
    ReportingWorkerService,
)
from app.services.storage.local_storage import LocalStorage

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


@dataclass(slots=True)
class ReportingApiContext:
    client: AsyncClient
    settings: Settings
    storage: LocalStorage


@pytest_asyncio.fixture
async def reporting_api(
    session_factory: TestSessionFactory,
    token_service: TokenService,
    tmp_path: Path,
) -> AsyncIterator[ReportingApiContext]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    settings = get_settings().model_copy(
        update={"storage_root": tmp_path / "report-storage"}
    )
    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_token_service] = (
        lambda: token_service
    )
    storage = LocalStorage(settings.storage_root)
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        yield ReportingApiContext(client, settings, storage)


async def _headers(
    create_user: UserFactory,
    token_service: TokenService,
    *,
    role: UserRole,
    email: str,
    department_id: UUID | None = None,
) -> tuple[User, dict[str, str]]:
    user = await create_user(
        role=role,
        email=email,
        department_id=department_id,
    )
    return user, {
        "Authorization": f"Bearer {token_service.create_access_token(user)}"
    }


async def _snapshot(
    session_factory: TestSessionFactory,
    *,
    generated_by: UUID | None,
    scope_department_id: UUID | None = None,
    report_name: str = "Operational Report",
    status: ReportSnapshotStatus = ReportSnapshotStatus.AVAILABLE,
    job_status: ReportJobStatus = ReportJobStatus.COMPLETED,
    file_format: ReportFileFormat = ReportFileFormat.JSON,
    expires_at: datetime | None = None,
    storage: LocalStorage | None = None,
    content: bytes | None = None,
    metadata: dict[str, object] | None = None,
) -> ReportSnapshot:
    snapshot_id = uuid4()
    storage_key = None
    file_size = None
    if storage is not None and content is not None:
        storage_key = (
            f"reports/snapshots/tests/{snapshot_id}.{file_format.value}"
        )
        result = await storage.save(BytesIO(content), storage_key)
        file_size = result["size"]
    now = datetime.now(UTC)
    snapshot = ReportSnapshot(
        id=snapshot_id,
        report_type=AdvancedReportType.COMPLIANCE_OVERVIEW,
        report_name=report_name,
        filters_json=AdvancedReportFilters().model_dump(
            mode="json", by_alias=True
        ),
        status=status,
        job_status=job_status,
        progress=100 if job_status is ReportJobStatus.COMPLETED else 0,
        current_stage=(
            "Completed"
            if job_status is ReportJobStatus.COMPLETED
            else "Queued"
        ),
        generated_by=generated_by,
        scope_department_id=scope_department_id,
        requested_at=now,
        started_at=(
            now if job_status is ReportJobStatus.COMPLETED else None
        ),
        generated_at=(
            now if job_status is ReportJobStatus.COMPLETED else None
        ),
        file_format=file_format,
        storage_key=storage_key,
        file_size=file_size,
        expires_at=expires_at,
        metadata_json=metadata or {},
    )
    async with session_factory() as session:
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)
    return snapshot


@pytest.mark.asyncio
async def test_authenticated_download_expiry_and_soft_delete_workflows(
    reporting_api: ReportingApiContext,
    session_factory: TestSessionFactory,
    create_user: UserFactory,
    token_service: TokenService,
) -> None:
    auditor, auditor_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.AUDITOR,
        email="report-download-auditor@example.com",
    )
    _, viewer_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.VIEWER,
        email="report-download-viewer@example.com",
    )
    now = datetime.now(UTC)
    available = await _snapshot(
        session_factory,
        generated_by=auditor.id,
        report_name="质量报告",
        expires_at=now + timedelta(days=1),
        storage=reporting_api.storage,
        content=b'{"private": true}',
    )
    expired = await _snapshot(
        session_factory,
        generated_by=auditor.id,
        expires_at=now - timedelta(seconds=1),
        storage=reporting_api.storage,
        content=b'{"expired": true}',
    )
    deletable = await _snapshot(
        session_factory,
        generated_by=auditor.id,
        expires_at=now + timedelta(days=1),
        storage=reporting_api.storage,
        content=b'{"delete": true}',
    )
    queued = await _snapshot(
        session_factory,
        generated_by=auditor.id,
        status=ReportSnapshotStatus.GENERATING,
        job_status=ReportJobStatus.QUEUED,
    )
    download_url = (
        f"/api/v1/reports/snapshots/{available.id}/download"
    )

    unauthenticated = await reporting_api.client.get(download_url)
    assert unauthenticated.status_code == 401
    unauthorized = await reporting_api.client.get(
        download_url, headers=viewer_headers
    )
    assert unauthorized.status_code == 403
    downloaded = await reporting_api.client.get(
        download_url, headers=auditor_headers
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b'{"private": true}'
    assert downloaded.headers["cache-control"] == "no-store"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    downloaded.headers["content-disposition"].encode("ascii")
    assert "advanced-report" in downloaded.headers["content-disposition"]

    expired_response = await reporting_api.client.get(
        f"/api/v1/reports/snapshots/{expired.id}/download",
        headers=auditor_headers,
    )
    assert expired_response.status_code == 410
    assert (
        expired_response.json()["errors"][0]["code"]
        == "REPORT_SNAPSHOT_EXPIRED"
    )

    deleted_response = await reporting_api.client.post(
        f"/api/v1/reports/snapshots/{deletable.id}/delete",
        headers=auditor_headers,
    )
    assert deleted_response.status_code == 200, deleted_response.text
    assert deleted_response.json()["data"]["status"] == "DELETED"
    queued_response = await reporting_api.client.post(
        f"/api/v1/reports/snapshots/{queued.id}/delete",
        headers=auditor_headers,
    )
    assert queued_response.status_code == 200

    async with session_factory() as session:
        expired_state = await session.get(ReportSnapshot, expired.id)
        deleted_state = await session.get(ReportSnapshot, deletable.id)
        queued_state = await session.get(ReportSnapshot, queued.id)
        assert expired_state is not None
        assert expired_state.status is ReportSnapshotStatus.EXPIRED
        assert deleted_state is not None
        assert deleted_state.status is ReportSnapshotStatus.DELETED
        assert deleted_state.storage_key is None
        assert (
            deleted_state.job_status is ReportJobStatus.COMPLETED
        )
        assert queued_state is not None
        assert queued_state.status is ReportSnapshotStatus.DELETED
        assert queued_state.job_status is ReportJobStatus.CANCELLED
    assert not await reporting_api.storage.exists(
        str(deletable.storage_key)
    )
    assert await reporting_api.storage.exists(
        f"reports/deleted/{deletable.id}.json"
    )


@pytest.mark.asyncio
async def test_schedule_update_scope_manual_run_and_disable(
    reporting_api: ReportingApiContext,
    session_factory: TestSessionFactory,
    create_user: UserFactory,
    token_service: TokenService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with session_factory() as session:
        own_department = Department(code="RPT", name="Reporting")
        other_department = Department(code="OTH", name="Other")
        session.add_all([own_department, other_department])
        await session.commit()
        own_id, other_id = own_department.id, other_department.id
    _, controller_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.DOCUMENT_CONTROLLER,
        email="report-schedule-controller@example.com",
        department_id=own_id,
    )
    _, own_viewer_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.REVIEWER,
        email="report-schedule-own@example.com",
        department_id=own_id,
    )
    _, other_viewer_headers = await _headers(
        create_user,
        token_service,
        role=UserRole.REVIEWER,
        email="report-schedule-other@example.com",
        department_id=other_id,
    )
    dispatched: list[UUID] = []

    def capture_dispatch(
        _service: AdvancedReportingService, snapshot_id: UUID
    ) -> None:
        dispatched.append(snapshot_id)

    monkeypatch.setattr(
        AdvancedReportingService, "_dispatch", capture_dispatch
    )
    invalid = await reporting_api.client.post(
        "/api/v1/reports/schedules",
        headers=controller_headers,
        json={
            "name": "Unsafe cron",
            "reportType": "COMPLIANCE_OVERVIEW",
            "formats": ["json"],
            "scheduleType": "CUSTOM_CRON",
            "cronExpression": "0 0 * * MON",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["errors"][0]["code"] == "REPORT_CRON_INVALID"

    created = await reporting_api.client.post(
        "/api/v1/reports/schedules",
        headers=controller_headers,
        json={
            "name": "Quality schedule",
            "reportType": "COMPLIANCE_OVERVIEW",
            "filters": {"departmentIds": [str(own_id)]},
            "formats": ["json", "xlsx", "pdf"],
            "scheduleType": "CUSTOM_CRON",
            "cronExpression": "*/15 * * * *",
            "timezone": "Asia/Makassar",
        },
    )
    assert created.status_code == 201, created.text
    schedule_id = UUID(created.json()["data"]["id"])

    own_list = await reporting_api.client.get(
        "/api/v1/reports/schedules",
        headers=own_viewer_headers,
    )
    other_list = await reporting_api.client.get(
        "/api/v1/reports/schedules",
        headers=other_viewer_headers,
    )
    assert own_list.status_code == 200
    assert own_list.json()["data"]["totalItems"] == 1
    assert other_list.status_code == 200
    assert other_list.json()["data"]["totalItems"] == 0

    updated = await reporting_api.client.put(
        f"/api/v1/reports/schedules/{schedule_id}",
        headers=controller_headers,
        json={
            "name": "Daily quality schedule",
            "scheduleType": "DAILY",
            "isActive": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["cronExpression"] == "0 0 * * *"
    assert updated.json()["data"]["isActive"] is False
    assert updated.json()["data"]["nextRunAt"] is None

    disabled_run = await reporting_api.client.post(
        f"/api/v1/reports/schedules/{schedule_id}/run",
        headers=controller_headers,
    )
    assert disabled_run.status_code == 409
    enabled = await reporting_api.client.put(
        f"/api/v1/reports/schedules/{schedule_id}",
        headers=controller_headers,
        json={"isActive": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["isActive"] is True
    assert enabled.json()["data"]["nextRunAt"] is not None

    run = await reporting_api.client.post(
        f"/api/v1/reports/schedules/{schedule_id}/run",
        headers=controller_headers,
    )
    assert run.status_code == 202, run.text
    job_ids = {UUID(value) for value in run.json()["data"]["jobIds"]}
    assert len(job_ids) == 3
    assert set(dispatched) == job_ids

    disabled = await reporting_api.client.post(
        f"/api/v1/reports/schedules/{schedule_id}/disable",
        headers=controller_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["isActive"] is False
    assert disabled.json()["data"]["nextRunAt"] is None

    async with session_factory() as session:
        schedule = await session.get(ReportSchedule, schedule_id)
        snapshots = list(
            await session.scalars(
                select(ReportSnapshot).where(
                    ReportSnapshot.id.in_(job_ids)
                )
            )
        )
        assert schedule is not None
        assert schedule.last_run_at is not None
        assert schedule.is_active is False
        assert {item.file_format for item in snapshots} == {
            ReportFileFormat.JSON,
            ReportFileFormat.XLSX,
            ReportFileFormat.PDF,
        }
        assert all(
            item.scope_department_id == own_id for item in snapshots
        )
        assert all(
            item.metadata_json["source"] == "SCHEDULE_MANUAL_RUN"
            for item in snapshots
        )


@pytest.mark.asyncio
async def test_worker_options_progress_failure_and_deleted_job_guard(
    session_factory: TestSessionFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(
        update={"storage_root": tmp_path / "worker-report-storage"}
    )
    storage = LocalStorage(settings.storage_root)
    success = await _snapshot(
        session_factory,
        generated_by=None,
        status=ReportSnapshotStatus.GENERATING,
        job_status=ReportJobStatus.QUEUED,
        metadata={
            "includeCharts": False,
            "includeDetailedTables": False,
        },
    )
    dataset = ReportDataset(
        report_type=AdvancedReportType.COMPLIANCE_OVERVIEW,
        summary={"documentsValidated": 1},
        data_series=[{"department": "RPT", "score": 90}],
        tables={"Details": [{"documentId": str(uuid4()), "score": 90}]},
    )

    async def build_dataset(
        _service: ReportDatasetService,
        _report_type: AdvancedReportType,
        _filters: AdvancedReportFilters,
    ) -> ReportDataset:
        return dataset

    monkeypatch.setattr(
        ReportDatasetService, "build", build_dataset
    )
    worker = ReportingWorkerService(
        settings,
        session_factory=session_factory,
        storage=storage,
    )
    result = await worker.process_snapshot(
        success.id, worker_reference="worker-success"
    )
    assert result is ReportJobStatus.COMPLETED
    async with session_factory() as session:
        successful_state = await session.get(ReportSnapshot, success.id)
        assert successful_state is not None
        assert successful_state.progress == 100
        assert successful_state.current_stage == "Completed"
        assert successful_state.storage_key is not None
        assert successful_state.dataset_hash is not None
        assert successful_state.metadata_json["tableCount"] == 0
        successful_key = successful_state.storage_key
    stream = await storage.open(successful_key)
    try:
        payload = json.loads(stream.read())
    finally:
        stream.close()
    assert payload["summary"] == {"documentsValidated": 1}
    assert payload["dataSeries"] == []
    assert payload["tableData"] == {}

    failed = await _snapshot(
        session_factory,
        generated_by=None,
        status=ReportSnapshotStatus.GENERATING,
        job_status=ReportJobStatus.QUEUED,
        metadata={
            "includeCharts": True,
            "includeDetailedTables": True,
        },
    )

    def fail_export(
        _service: ReportExportService,
        *_args: object,
        **_kwargs: object,
    ) -> bytes:
        raise RuntimeError("private internal failure detail")

    monkeypatch.setattr(ReportExportService, "build", fail_export)
    failed_result = await worker.process_snapshot(
        failed.id, worker_reference="worker-failure"
    )
    assert failed_result is ReportJobStatus.FAILED
    async with session_factory() as session:
        failed_state = await session.get(ReportSnapshot, failed.id)
        assert failed_state is not None
        assert failed_state.status is ReportSnapshotStatus.FAILED
        assert failed_state.job_status is ReportJobStatus.FAILED
        assert 0 < failed_state.progress < 100
        assert failed_state.current_stage == "Failed"
        assert failed_state.error_code == "REPORT_GENERATION_FAILED"
        assert "private internal failure detail" not in str(
            failed_state.error_message
        )

    deleted = await _snapshot(
        session_factory,
        generated_by=None,
        status=ReportSnapshotStatus.DELETED,
        job_status=ReportJobStatus.QUEUED,
    )
    deleted_result = await worker.process_snapshot(
        deleted.id, worker_reference="worker-deleted"
    )
    assert deleted_result is ReportJobStatus.CANCELLED
    async with session_factory() as session:
        deleted_state = await session.get(ReportSnapshot, deleted.id)
        assert deleted_state is not None
        assert deleted_state.status is ReportSnapshotStatus.DELETED
        assert deleted_state.job_status is ReportJobStatus.CANCELLED
        assert deleted_state.storage_key is None


def test_xlsx_large_dataset_limit_is_enforced() -> None:
    dataset = ReportDataset(
        report_type=AdvancedReportType.COMPLIANCE_OVERVIEW,
        summary={},
        tables={"Details": [{"value": 1}, {"value": 2}]},
    )

    with pytest.raises(
        ValueError, match="exceeds the XLSX row limit"
    ):
        ReportXlsxService(maximum_rows=1).build(
            dataset,
            report_name="Bounded report",
            filters=AdvancedReportFilters(),
        )
