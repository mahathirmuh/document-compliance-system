"""Regression coverage for Phase 8 worker dispatch and retry boundaries."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, ClassVar
from uuid import UUID, uuid4

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.core.config import get_settings
from app.models.compliance_enums import ComplianceJobStatus
from app.services.compliance.compliance_context_service import (
    ComplianceContextBuildError,
)
from app.services.compliance.compliance_job_service import (
    ComplianceJobService,
)
from app.services.compliance.compliance_pipeline import (
    COMPLIANCE_GROUPING_FAILED,
    COMPLIANCE_SECTION_DETECTION_FAILED,
    COMPLIANCE_VALIDATION_FAILED,
    CompliancePipelineStageError,
)
from app.services.compliance.compliance_worker_service import (
    ComplianceWorkerService,
    TransientComplianceWorkerError,
)
from app.workers import compliance_tasks


def _lease_errors() -> list[BaseException]:
    return [
        SQLAlchemyError("synthetic SQLAlchemy lease failure"),
        DBAPIError(
            "SELECT pg_try_advisory_lock(:lease_key)",
            {},
            RuntimeError("synthetic DBAPI lease failure"),
        ),
        OSError("synthetic lease transport failure"),
    ]


class _FailingContext:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def __aenter__(self) -> Any:
        raise self.error

    async def __aexit__(self, *_: object) -> None:
        return None


class _PostgresBind:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def connect(self) -> _FailingContext:
        return _FailingContext(self.error)


class _LeaseAcquisitionSessionFactory:
    def __init__(self, error: BaseException) -> None:
        self.kw = {"bind": _PostgresBind(error)}


class _BusyLeaseSessionFactory:
    kw: ClassVar[dict[str, object]] = {}

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __call__(self) -> _FailingContext:
        return _FailingContext(self.error)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lease_error",
    _lease_errors(),
    ids=["sqlalchemy", "dbapi", "oserror"],
)
async def test_advisory_lease_acquisition_errors_are_transient(
    lease_error: BaseException,
) -> None:
    worker = ComplianceWorkerService(
        get_settings(),
        session_factory=_LeaseAcquisitionSessionFactory(lease_error),
    )

    with pytest.raises(TransientComplianceWorkerError) as exc_info:
        await worker.process_job(
            uuid4(),
            worker_reference="lease-acquisition-test",
            attempt_number=1,
        )

    assert exc_info.value.__cause__ is lease_error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "session_error",
    _lease_errors(),
    ids=["sqlalchemy", "dbapi", "oserror"],
)
async def test_busy_lease_session_read_errors_are_transient(
    session_error: BaseException,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = ComplianceWorkerService(
        get_settings(),
        session_factory=_BusyLeaseSessionFactory(session_error),
    )

    @asynccontextmanager
    async def busy_lease(_: UUID):
        yield False

    monkeypatch.setattr(worker, "_execution_lease", busy_lease)

    with pytest.raises(TransientComplianceWorkerError) as exc_info:
        await worker.process_job(
            uuid4(),
            worker_reference="busy-lease-test",
            attempt_number=1,
        )

    assert exc_info.value.__cause__ is session_error


@pytest.mark.asyncio
async def test_worker_service_propagates_soft_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            return None

    class SessionFactory:
        kw: ClassVar[dict[str, object]] = {}

        def __call__(self) -> SessionContext:
            return SessionContext()

    worker = ComplianceWorkerService(
        get_settings(),
        session_factory=SessionFactory(),
    )
    job_id = uuid4()
    job = SimpleNamespace(
        id=job_id,
        status=ComplianceJobStatus.QUEUED,
    )
    failed_jobs: list[UUID] = []

    async def start_job(*_: object, **__: object):
        return job, True

    async def load_context(*_: object, **__: object):
        return object(), []

    async def set_progress(*_: object, **__: object) -> None:
        return None

    async def timeout_pipeline(*_: object, **__: object):
        raise SoftTimeLimitExceeded

    async def fail_job(failed_job_id: UUID, **_: object) -> None:
        failed_jobs.append(failed_job_id)

    monkeypatch.setattr(worker, "_start_job", start_job)
    monkeypatch.setattr(worker, "_load_context", load_context)
    monkeypatch.setattr(worker, "_set_progress", set_progress)
    monkeypatch.setattr(worker.pipeline, "run", timeout_pipeline)
    monkeypatch.setattr(worker, "fail_job", fail_job)

    with pytest.raises(SoftTimeLimitExceeded):
        await worker._process_job(
            job_id,
            worker_reference="soft-timeout-test",
            attempt_number=1,
        )

    assert failed_jobs == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stage_code", "public_message"),
    [
        (
            COMPLIANCE_SECTION_DETECTION_FAILED,
            "Document section detection could not be completed.",
        ),
        (
            COMPLIANCE_GROUPING_FAILED,
            "Multilingual content grouping could not be completed.",
        ),
        (
            COMPLIANCE_VALIDATION_FAILED,
            "Compliance validation could not be completed.",
        ),
    ],
)
async def test_worker_records_stable_pipeline_stage_failure(
    stage_code: str,
    public_message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            return None

    class SessionFactory:
        kw: ClassVar[dict[str, object]] = {}

        def __call__(self) -> SessionContext:
            return SessionContext()

    worker = ComplianceWorkerService(
        get_settings(),
        session_factory=SessionFactory(),
    )
    job_id = uuid4()
    job = SimpleNamespace(
        id=job_id,
        status=ComplianceJobStatus.QUEUED,
    )
    failures: list[tuple[UUID, str, str]] = []

    async def start_job(*_: object, **__: object):
        return job, True

    async def load_context(*_: object, **__: object):
        return object(), []

    async def set_progress(*_: object, **__: object) -> None:
        return None

    async def fail_pipeline(*_: object, **__: object):
        try:
            raise RuntimeError("private stage implementation detail")
        except RuntimeError as exc:
            raise CompliancePipelineStageError(
                stage_code,
                public_message,
            ) from exc

    async def fail_job(
        failed_job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        failures.append((failed_job_id, error_code, error_message))

    monkeypatch.setattr(worker, "_start_job", start_job)
    monkeypatch.setattr(worker, "_load_context", load_context)
    monkeypatch.setattr(worker, "_set_progress", set_progress)
    monkeypatch.setattr(worker.pipeline, "run", fail_pipeline)
    monkeypatch.setattr(worker, "fail_job", fail_job)

    status = await worker._process_job(
        job_id,
        worker_reference="stage-error-test",
        attempt_number=1,
    )

    assert status is ComplianceJobStatus.FAILED
    assert failures == [(job_id, stage_code, public_message)]
    assert "private stage implementation detail" not in failures[0][2]


@pytest.mark.asyncio
async def test_worker_records_stable_context_build_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            return None

    class SessionFactory:
        kw: ClassVar[dict[str, object]] = {}

        def __call__(self) -> SessionContext:
            return SessionContext()

    worker = ComplianceWorkerService(
        get_settings(),
        session_factory=SessionFactory(),
    )
    job_id = uuid4()
    job = SimpleNamespace(
        id=job_id,
        status=ComplianceJobStatus.QUEUED,
    )
    failures: list[tuple[UUID, str, str]] = []

    async def start_job(*_: object, **__: object):
        return job, True

    async def fail_context_build(*_: object, **__: object):
        raise ComplianceContextBuildError("private malformed source and rule details")

    async def fail_job(
        failed_job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        failures.append((failed_job_id, error_code, error_message))

    monkeypatch.setattr(worker, "_start_job", start_job)
    monkeypatch.setattr(worker, "_load_context", fail_context_build)
    monkeypatch.setattr(worker, "fail_job", fail_job)

    status = await worker._process_job(
        job_id,
        worker_reference="context-error-test",
        attempt_number=1,
    )

    assert status is ComplianceJobStatus.FAILED
    assert failures == [
        (
            job_id,
            "COMPLIANCE_CONTEXT_BUILD_FAILED",
            "Compliance validation context could not be prepared.",
        )
    ]
    assert "private malformed source" not in failures[0][2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "private_error",
    [
        TypeError("private validation type detail"),
        RuntimeError("private unexpected worker detail"),
    ],
    ids=["type-error", "unexpected-error"],
)
async def test_worker_does_not_persist_generic_exception_details(
    private_error: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_: object) -> None:
            return None

    class SessionFactory:
        kw: ClassVar[dict[str, object]] = {}

        def __call__(self) -> SessionContext:
            return SessionContext()

    worker = ComplianceWorkerService(
        get_settings(),
        session_factory=SessionFactory(),
    )
    job_id = uuid4()
    job = SimpleNamespace(
        id=job_id,
        status=ComplianceJobStatus.QUEUED,
    )
    failures: list[tuple[UUID, str, str]] = []

    async def start_job(*_: object, **__: object):
        return job, True

    async def load_context(*_: object, **__: object):
        return object(), []

    async def set_progress(*_: object, **__: object) -> None:
        return None

    async def fail_pipeline(*_: object, **__: object):
        raise private_error

    async def fail_job(
        failed_job_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        failures.append((failed_job_id, error_code, error_message))

    monkeypatch.setattr(worker, "_start_job", start_job)
    monkeypatch.setattr(worker, "_load_context", load_context)
    monkeypatch.setattr(worker, "_set_progress", set_progress)
    monkeypatch.setattr(worker.pipeline, "run", fail_pipeline)
    monkeypatch.setattr(worker, "fail_job", fail_job)

    status = await worker._process_job(
        job_id,
        worker_reference="generic-error-test",
        attempt_number=1,
    )

    assert status is ComplianceJobStatus.FAILED
    assert failures == [
        (
            job_id,
            COMPLIANCE_VALIDATION_FAILED,
            "Compliance validation could not be completed.",
        )
    ]
    assert str(private_error) not in failures[0][2]


def test_compliance_task_records_soft_time_limit_as_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    failures: list[tuple[UUID, str, str]] = []

    class TimeoutWorker:
        def __init__(self, _: object) -> None:
            pass

        async def process_job(self, *_: object, **__: object):
            raise SoftTimeLimitExceeded

        async def fail_job(
            self,
            failed_job_id: UUID,
            *,
            error_code: str,
            error_message: str,
        ) -> None:
            failures.append((failed_job_id, error_code, error_message))

    monkeypatch.setattr(
        compliance_tasks,
        "ComplianceWorkerService",
        TimeoutWorker,
    )

    result = compliance_tasks.process_compliance_job.run(str(job_id))

    assert result == {
        "jobId": str(job_id),
        "status": ComplianceJobStatus.FAILED.value,
    }
    assert failures == [
        (
            job_id,
            "COMPLIANCE_TIMEOUT",
            "Compliance validation exceeded the configured time limit.",
        )
    ]


@pytest.mark.asyncio
async def test_dispatch_preserves_worker_claim_made_during_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = SimpleNamespace(
        id=uuid4(),
        error_details_json={"revalidationReason": "retry race"},
    )

    class DispatchSession:
        def __init__(self) -> None:
            self.commit_count = 0
            self.persisted_details = dict(job.error_details_json)

        async def commit(self) -> None:
            self.commit_count += 1
            self.persisted_details = dict(job.error_details_json)

        async def rollback(self) -> None:
            return None

    session = DispatchSession()
    published: dict[str, Any] = {}

    def claim_job_during_publish(**kwargs: Any) -> SimpleNamespace:
        published.update(kwargs)
        session.persisted_details["workerAttempt"] = 1
        return SimpleNamespace(id=kwargs.get("task_id", "celery-task-id"))

    monkeypatch.setattr(
        compliance_tasks.process_compliance_job,
        "apply_async",
        claim_job_during_publish,
    )
    service = SimpleNamespace(
        session=session,
        settings=SimpleNamespace(compliance_queue_name="compliance"),
    )

    await ComplianceJobService._dispatch(service, job)

    task_id = published["task_id"]
    assert published["args"] == [str(job.id)]
    assert published["queue"] == "compliance"
    assert session.commit_count == 1
    assert session.persisted_details == {
        "revalidationReason": "retry race",
        "workerReference": task_id,
        "workerAttempt": 1,
    }
