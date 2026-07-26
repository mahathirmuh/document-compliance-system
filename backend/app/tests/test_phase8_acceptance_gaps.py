"""Acceptance coverage for remaining Phase 8 backend contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import UserRole
from app.core.config import get_settings
from app.models.compliance_enums import ComplianceJobStatus
from app.models.compliance_job import ComplianceJob
from app.models.compliance_run import ComplianceRun
from app.models.document_file import DocumentFile
from app.models.finding_occurrence import FindingOccurrence
from app.models.validation_finding import ValidationFinding
from app.models.validation_rule import ValidationRule
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.services.auth.token_service import TokenService
from app.services.compliance.compliance_status_service import (
    ComplianceStatusService,
)
from app.services.compliance.compliance_worker_service import (
    ComplianceWorkerService,
)
from app.services.language.language_persistence_service import (
    LanguagePersistenceService,
)
from app.services.language.language_runtime_config import (
    LanguageRuntimeConfig,
)
from app.tests.test_phase7_language_persistence import (
    _language_job,
    _pipeline,
    _source_graph,
)
from app.workers.compliance_tasks import process_compliance_job

TestSessionFactory = async_sessionmaker[AsyncSession]


def _headers(user: object, tokens: TokenService) -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {tokens.create_access_token(user)}"  # type: ignore[arg-type]
        )
    }


def _error_code(response: object) -> str | None:
    payload = response.json()  # type: ignore[union-attr]
    return payload["errors"][0]["code"]


def _rule(
    *,
    code: str,
    document_type_id: UUID,
    required_languages: list[str] | None = None,
    required_sections: list[str] | None = None,
    is_default: bool = False,
) -> ValidationRule:
    languages = required_languages or ["id", "en", "zh"]
    sections = required_sections or []
    zero_coverage = {language: 0 for language in languages}
    return ValidationRule(
        code=code,
        name=f"Acceptance rule {code}",
        document_type_id=document_type_id,
        required_languages_json=languages,
        required_sections_json=sections,
        language_order_json=languages,
        minimum_language_block_coverage_json=zero_coverage,
        minimum_language_character_coverage_json=zero_coverage,
        validate_sections=bool(sections),
        validate_language_order=False,
        validate_translation_groups=False,
        validate_tables=False,
        validate_cells=False,
        validation_options_json={
            "presenceMinimumBlocks": 1,
            "presenceMinimumCharacters": 10,
        },
        is_default=is_default,
        is_active=True,
    )


def _uniquify_source(graph: tuple[object, ...], ordinal: int) -> None:
    (
        document,
        revision,
        document_file,
        _extraction_job,
        extraction_run,
        _container,
        _block,
    ) = graph
    document.document_number = f"8{ordinal:02d}"  # type: ignore[attr-defined]
    document.base_document_code = (  # type: ignore[attr-defined]
        f"MTI-HRM-POL-8{ordinal:02d}"
    )
    document.title = f"Phase 8 acceptance source {ordinal}"  # type: ignore[attr-defined]
    revision.full_document_code = (  # type: ignore[attr-defined]
        f"MTI-HRM-POL-8{ordinal:02d}_Rev.000"
    )
    document_file.original_filename = (  # type: ignore[attr-defined]
        f"MTI-HRM-POL-8{ordinal:02d}_Rev.000.pdf"
    )
    document_file.sanitized_filename = (  # type: ignore[attr-defined]
        f"MTI-HRM-POL-8{ordinal:02d}_Rev.000.pdf"
    )
    document_file.storage_key = (  # type: ignore[attr-defined]
        f"documents/originals/phase8/acceptance-{ordinal}.pdf"
    )
    document_file.sha256_hash = f"{ordinal:x}" * 64  # type: ignore[attr-defined]
    extraction_run.source_sha256_hash = (  # type: ignore[attr-defined]
        f"{ordinal:x}" * 64
    )
    extraction_run.content_hash = (  # type: ignore[attr-defined]
        f"{ordinal + 8:x}" * 64
    )


async def _seed_ready_source(
    session_factory: TestSessionFactory,
    *,
    ordinal: int,
    include_alternate_rule: bool = False,
) -> SimpleNamespace:
    graph = _source_graph()
    _uniquify_source(graph, ordinal)
    (
        document,
        revision,
        document_file,
        extraction_job,
        extraction_run,
        container,
        block,
    ) = graph
    primary_rule = _rule(
        code=f"P8-ACCEPT-{ordinal}A",
        document_type_id=document.document_type_id,
        is_default=True,
    )
    alternate_rule = (
        _rule(
            code=f"P8-ACCEPT-{ordinal}B",
            document_type_id=document.document_type_id,
            required_languages=["en"],
        )
        if include_alternate_rule
        else None
    )
    config = LanguageRuntimeConfig(database_batch_size=1)
    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                container,
                block,
                primary_rule,
                *([alternate_rule] if alternate_rule is not None else []),
            ]
        )
        await session.flush()
        revision.validation_rule_id = primary_rule.id
        document_file.latest_extraction_run_id = extraction_run.id
        language_job = _language_job(
            document,
            revision,
            document_file,
            extraction_run,
        )
        session.add(language_job)
        await session.flush()
        language_run = await LanguagePersistenceService(
            session,
            config,
        ).persist_result(
            job=language_job,
            result=_pipeline(
                extraction_run,
                container,
                block,
                config,
            ),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        await session.commit()

    return SimpleNamespace(
        document_id=document.id,
        document_file_id=document_file.id,
        extraction_run_id=extraction_run.id,
        language_run_id=language_run.id,
        primary_rule_id=primary_rule.id,
        alternate_rule_id=(
            alternate_rule.id if alternate_rule is not None else None
        ),
        department_id=document.department_id,
    )


async def _process_job(
    job_id: str,
    *,
    session_factory: TestSessionFactory,
    worker_reference: str,
) -> ComplianceJobStatus:
    return await ComplianceWorkerService(
        get_settings(),
        session_factory=session_factory,
    ).process_job(
        UUID(job_id),
        worker_reference=worker_reference,
        attempt_number=1,
    )


@pytest.mark.asyncio
async def test_validation_prerequisites_return_the_exact_public_codes(
    api_client: AsyncClient,
    create_user,
    session_factory: TestSessionFactory,
    token_service: TokenService,
) -> None:
    graph = _source_graph()
    _uniquify_source(graph, 1)
    (
        document,
        revision,
        document_file,
        extraction_job,
        extraction_run,
        container,
        block,
    ) = graph
    rule = _rule(
        code="P8-PREREQUISITES",
        document_type_id=document.document_type_id,
        is_default=True,
    )
    user = await create_user(
        name="Prerequisite Controller",
        email="phase8.prerequisites@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=document.department_id,
    )
    headers = _headers(user, token_service)
    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                extraction_job,
                extraction_run,
                container,
                block,
                rule,
            ]
        )
        await session.flush()
        revision.validation_rule_id = rule.id
        await session.commit()

    extraction_missing = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=headers,
        json={"documentFileId": str(document_file.id)},
    )
    assert extraction_missing.status_code == 400
    assert _error_code(extraction_missing) == "COMPLIANCE_EXTRACTION_REQUIRED"

    async with session_factory() as session:
        persisted_file = await session.get(DocumentFile, document_file.id)
        assert persisted_file is not None
        persisted_file.latest_extraction_run_id = extraction_run.id
        await session.commit()

    language_missing = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=headers,
        json={"documentFileId": str(document_file.id)},
    )
    assert language_missing.status_code == 400
    assert _error_code(language_missing) == (
        "COMPLIANCE_LANGUAGE_DETECTION_REQUIRED"
    )

    config = LanguageRuntimeConfig(database_batch_size=1)
    async with session_factory() as session:
        persisted_document = await session.get(type(document), document.id)
        persisted_revision = await session.get(type(revision), revision.id)
        persisted_file = await session.get(DocumentFile, document_file.id)
        persisted_extraction = await session.get(
            type(extraction_run),
            extraction_run.id,
        )
        persisted_container = await session.get(type(container), container.id)
        persisted_block = await session.get(type(block), block.id)
        assert all(
            item is not None
            for item in (
                persisted_document,
                persisted_revision,
                persisted_file,
                persisted_extraction,
                persisted_container,
                persisted_block,
            )
        )
        persisted_extraction.requires_ocr = True  # type: ignore[union-attr]
        language_job = _language_job(
            persisted_document,
            persisted_revision,
            persisted_file,
            persisted_extraction,
        )
        session.add(language_job)
        await session.flush()
        await LanguagePersistenceService(session, config).persist_result(
            job=language_job,
            result=_pipeline(
                persisted_extraction,
                persisted_container,
                persisted_block,
                config,
            ),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        await session.commit()

    ocr_missing = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=headers,
        json={"documentFileId": str(document_file.id)},
    )
    assert ocr_missing.status_code == 400
    assert _error_code(ocr_missing) == "COMPLIANCE_OCR_REQUIRED"


@pytest.mark.asyncio
async def test_duplicate_active_validation_returns_conflict_without_extra_job(
    api_client: AsyncClient,
    create_user,
    session_factory: TestSessionFactory,
    token_service: TokenService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = await _seed_ready_source(session_factory, ordinal=2)
    user = await create_user(
        name="Duplicate Job Controller",
        email="phase8.duplicate@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=source.department_id,
    )
    monkeypatch.setattr(
        process_compliance_job,
        "apply_async",
        lambda **_: SimpleNamespace(id="phase8-duplicate-task"),
    )
    payload = {"documentFileId": str(source.document_file_id)}
    first = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=_headers(user, token_service),
        json=payload,
    )
    duplicate = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=_headers(user, token_service),
        json=payload,
    )

    assert first.status_code == 202
    assert duplicate.status_code == 409
    assert _error_code(duplicate) == "COMPLIANCE_ACTIVE_JOB_EXISTS"
    async with session_factory() as session:
        assert await session.scalar(
            select(func.count()).select_from(ComplianceJob)
        ) == 1


@pytest.mark.asyncio
async def test_revalidation_with_another_rule_retains_both_snapshots_and_compares(
    api_client: AsyncClient,
    create_user,
    session_factory: TestSessionFactory,
    token_service: TokenService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = await _seed_ready_source(
        session_factory,
        ordinal=3,
        include_alternate_rule=True,
    )
    user = await create_user(
        name="Revalidation Controller",
        email="phase8.revalidation@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=source.department_id,
    )
    headers = _headers(user, token_service)
    monkeypatch.setattr(
        process_compliance_job,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )

    queued = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=headers,
        json={"documentFileId": str(source.document_file_id)},
    )
    assert queued.status_code == 202
    initial_job_id = queued.json()["data"]["jobId"]
    assert (
        await _process_job(
            initial_job_id,
            session_factory=session_factory,
            worker_reference="phase8-initial-acceptance",
        )
        in {
            ComplianceJobStatus.COMPLETED,
            ComplianceJobStatus.PARTIALLY_COMPLETED,
        }
    )
    initial_job = await api_client.get(
        f"/api/v1/compliance/jobs/{initial_job_id}",
        headers=headers,
    )
    initial_run_id = initial_job.json()["data"]["resultSummary"]["runId"]

    revalidated = await api_client.post(
        f"/api/v1/compliance/runs/{initial_run_id}/revalidate",
        headers=headers,
        json={
            "reason": "Evaluate the retained source against the English-only rule.",
            "validationRuleId": str(source.alternate_rule_id),
        },
    )
    assert revalidated.status_code == 202
    revalidation_job_id = revalidated.json()["data"]["jobId"]
    assert (
        await _process_job(
            revalidation_job_id,
            session_factory=session_factory,
            worker_reference="phase8-revalidation-acceptance",
        )
        in {
            ComplianceJobStatus.COMPLETED,
            ComplianceJobStatus.PARTIALLY_COMPLETED,
        }
    )
    revalidation_job = await api_client.get(
        f"/api/v1/compliance/jobs/{revalidation_job_id}",
        headers=headers,
    )
    revalidated_run_id = revalidation_job.json()["data"]["resultSummary"][
        "runId"
    ]

    async with session_factory() as session:
        retained = list(
            await session.scalars(
                select(ComplianceRun)
                .where(ComplianceRun.document_file_id == source.document_file_id)
                .order_by(ComplianceRun.created_at)
            )
        )
        latest_pointer = await session.scalar(
            select(DocumentFile.latest_compliance_run_id).where(
                DocumentFile.id == source.document_file_id
            )
        )
    assert len(retained) == 2
    by_id = {run.id: run for run in retained}
    initial_run = by_id[UUID(initial_run_id)]
    revalidated_run = by_id[UUID(revalidated_run_id)]
    assert initial_run.validation_rule_id == source.primary_rule_id
    assert revalidated_run.validation_rule_id == source.alternate_rule_id
    assert initial_run.rule_snapshot_json["requiredLanguages"] == [
        "id",
        "en",
        "zh",
    ]
    assert revalidated_run.rule_snapshot_json["requiredLanguages"] == ["en"]
    assert initial_run.rule_snapshot_json["ruleId"] == str(
        source.primary_rule_id
    )
    assert revalidated_run.rule_snapshot_json["ruleId"] == str(
        source.alternate_rule_id
    )
    assert latest_pointer == UUID(revalidated_run_id)

    comparison = await api_client.get(
        (
            f"/api/v1/compliance/runs/{revalidated_run_id}"
            f"/compare/{initial_run_id}"
        ),
        headers=headers,
    )
    assert comparison.status_code == 200
    assert comparison.json()["data"]["currentRunId"] == revalidated_run_id
    assert comparison.json()["data"]["previousRunId"] == initial_run_id

    other_source = await _seed_ready_source(session_factory, ordinal=4)
    other_queued = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=headers,
        json={"documentFileId": str(other_source.document_file_id)},
    )
    assert other_queued.status_code == 202
    other_job_id = other_queued.json()["data"]["jobId"]
    assert (
        await _process_job(
            other_job_id,
            session_factory=session_factory,
            worker_reference="phase8-other-document-acceptance",
        )
        in {
            ComplianceJobStatus.COMPLETED,
            ComplianceJobStatus.PARTIALLY_COMPLETED,
        }
    )
    other_job = await api_client.get(
        f"/api/v1/compliance/jobs/{other_job_id}",
        headers=headers,
    )
    other_run_id = other_job.json()["data"]["resultSummary"]["runId"]
    cross_document = await api_client.get(
        (
            f"/api/v1/compliance/runs/{revalidated_run_id}"
            f"/compare/{other_run_id}"
        ),
        headers=headers,
    )
    assert cross_document.status_code == 400
    assert _error_code(cross_document) == (
        "COMPLIANCE_COMPARISON_DOCUMENT_MISMATCH"
    )


def test_fail_on_missing_language_and_section_controls_status_precedence() -> None:
    service = ComplianceStatusService()

    strict_language = service.determine(
        100,
        context=SimpleNamespace(
            prerequisites={},
            missing_languages=["zh"],
            missing_sections=[],
        ),
        rule=SimpleNamespace(
            fail_on_missing_required_language=True,
            fail_on_missing_required_section=False,
            fail_on_critical_finding=True,
            compliant_score=95,
            partially_compliant_score=70,
        ),
    )
    advisory_language = service.determine(
        100,
        context=SimpleNamespace(
            prerequisites={},
            missing_languages=["zh"],
            missing_sections=[],
        ),
        rule=SimpleNamespace(
            fail_on_missing_required_language=False,
            fail_on_missing_required_section=False,
            fail_on_critical_finding=True,
            compliant_score=95,
            partially_compliant_score=70,
        ),
    )
    strict_section = service.determine(
        100,
        context=SimpleNamespace(
            prerequisites={},
            missing_languages=[],
            missing_sections=["PURPOSE"],
        ),
        rule=SimpleNamespace(
            fail_on_missing_required_language=False,
            fail_on_missing_required_section=True,
            fail_on_critical_finding=True,
            compliant_score=95,
            partially_compliant_score=70,
        ),
    )
    advisory_section = service.determine(
        100,
        context=SimpleNamespace(
            prerequisites={},
            missing_languages=[],
            missing_sections=["PURPOSE"],
        ),
        rule=SimpleNamespace(
            fail_on_missing_required_language=False,
            fail_on_missing_required_section=False,
            fail_on_critical_finding=True,
            compliant_score=95,
            partially_compliant_score=70,
        ),
    )

    assert strict_language.status == "NON_COMPLIANT"
    assert strict_language.reasons == ("MISSING_REQUIRED_LANGUAGE",)
    assert advisory_language.status == "PARTIALLY_COMPLIANT"
    assert advisory_language.reasons == ("MISSING_REQUIRED_LANGUAGE",)
    assert strict_section.status == "NON_COMPLIANT"
    assert strict_section.reasons == ("MISSING_REQUIRED_SECTION",)
    assert advisory_section.status == "COMPLIANT"
    assert advisory_section.reasons == ()


@pytest.mark.asyncio
async def test_persistence_failure_rolls_back_run_children_and_latest_pointer(
    api_client: AsyncClient,
    create_user,
    session_factory: TestSessionFactory,
    token_service: TokenService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = await _seed_ready_source(session_factory, ordinal=5)
    user = await create_user(
        name="Rollback Controller",
        email="phase8.rollback@example.com",
        role=UserRole.DOCUMENT_CONTROLLER,
        department_id=source.department_id,
    )
    headers = _headers(user, token_service)
    monkeypatch.setattr(
        process_compliance_job,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )
    queued = await api_client.post(
        "/api/v1/compliance/jobs",
        headers=headers,
        json={"documentFileId": str(source.document_file_id)},
    )
    assert queued.status_code == 202
    job_id = queued.json()["data"]["jobId"]

    original_set_latest = ComplianceRunRepository.set_latest_for_file
    observed_inside_transaction: dict[str, object] = {}

    async def fail_after_all_result_rows_and_pointer_are_written(
        repository: ComplianceRunRepository,
        *,
        document_file_id: UUID,
        compliance_run_id: UUID,
    ) -> None:
        await original_set_latest(
            repository,
            document_file_id=document_file_id,
            compliance_run_id=compliance_run_id,
        )
        observed_inside_transaction["runs"] = await repository.session.scalar(
            select(func.count()).select_from(ComplianceRun)
        )
        observed_inside_transaction[
            "findings"
        ] = await repository.session.scalar(
            select(func.count()).select_from(ValidationFinding)
        )
        observed_inside_transaction[
            "occurrences"
        ] = await repository.session.scalar(
            select(func.count()).select_from(FindingOccurrence)
        )
        observed_inside_transaction[
            "latest"
        ] = await repository.session.scalar(
            select(DocumentFile.latest_compliance_run_id).where(
                DocumentFile.id == document_file_id
            )
        )
        raise SQLAlchemyError("synthetic failure after latest pointer update")

    monkeypatch.setattr(
        ComplianceRunRepository,
        "set_latest_for_file",
        fail_after_all_result_rows_and_pointer_are_written,
    )
    status = await _process_job(
        job_id,
        session_factory=session_factory,
        worker_reference="phase8-rollback-acceptance",
    )

    assert status is ComplianceJobStatus.FAILED
    assert observed_inside_transaction["runs"] == 1
    assert int(observed_inside_transaction["findings"]) > 0
    assert int(observed_inside_transaction["occurrences"]) > 0
    assert observed_inside_transaction["latest"] is not None

    async with session_factory() as session:
        assert await session.scalar(
            select(func.count()).select_from(ComplianceRun)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(ValidationFinding)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(FindingOccurrence)
        ) == 0
        assert (
            await session.scalar(
                select(DocumentFile.latest_compliance_run_id).where(
                    DocumentFile.id == source.document_file_id
                )
            )
            is None
        )
        failed_job = await session.get(ComplianceJob, UUID(job_id))
        assert failed_job is not None
        assert failed_job.status is ComplianceJobStatus.FAILED
        assert failed_job.error_code == "COMPLIANCE_PERSISTENCE_FAILED"
