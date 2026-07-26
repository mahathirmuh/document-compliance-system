"""Regression coverage for bounded Phase 8 retained-result reads."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from inspect import signature
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1.endpoints import compliance as compliance_endpoints
from app.api.v1.endpoints.compliance import (
    list_compliance_run_findings,
    list_compliance_sections,
    list_compliance_translation_groups,
)
from app.core.authorization import UserRole
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.main import app
from app.models.compliance_enums import ComplianceStatus
from app.repositories.compliance_job_repository import ComplianceJobRepository
from app.repositories.compliance_run_repository import (
    ComplianceRunRepository,
)
from app.repositories.detected_section_repository import (
    DetectedSectionRepository,
)
from app.repositories.translation_group_repository import (
    TranslationGroupRepository,
)
from app.repositories.validation_finding_repository import (
    ValidationFindingRepository,
)
from app.schemas.finding import FindingListResponse
from app.schemas.section_detection import (
    DetectedSectionListResponse,
    DetectedSectionResponse,
)
from app.schemas.translation_group import (
    TranslationGroupListResponse,
    TranslationGroupResponse,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.compliance.compliance_query_service import (
    ComplianceQueryService,
    compliance_finding_list_item,
    translation_group_response,
)
from app.services.compliance.compliance_result_export_service import (
    ComplianceResultExportService,
)
from app.services.compliance.compliance_worker_service import (
    ComplianceWorkerService,
)


class _Rows:
    def __init__(self, rows: list[object] | None = None) -> None:
        self._rows = rows or []

    def unique(self) -> _Rows:
        return self

    def all(self) -> list[object]:
        return self._rows


def _relationship_strategy(statement, relationship: str):
    for option in statement._with_options:
        if f"ComplianceRun.{relationship}" in str(option.path):
            return option.context[0].strategy
    raise AssertionError(f"No loader strategy found for {relationship}.")


def _compiled(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_compliance_run_heavy_children_are_opt_in() -> None:
    repository = ComplianceRunRepository(Mock())

    default = repository.base_statement()
    explicit = repository.base_statement(
        include_detected_sections=True,
        include_translation_groups=True,
    )

    assert _relationship_strategy(default, "detected_sections") == (("lazy", "raise"),)
    assert _relationship_strategy(default, "translation_groups") == (("lazy", "raise"),)
    assert _relationship_strategy(explicit, "detected_sections") == (
        ("lazy", "selectin"),
    )
    assert _relationship_strategy(explicit, "translation_groups") == (
        ("lazy", "selectin"),
    )


@pytest.mark.asyncio
async def test_run_section_and_finding_queries_apply_limit_before_fetch() -> None:
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=73),
        scalars=AsyncMock(return_value=_Rows()),
    )
    run_id = uuid4()

    await DetectedSectionRepository(session).list_for_run(  # type: ignore[arg-type]
        run_id,
        page=3,
        page_size=17,
    )
    await ValidationFindingRepository(session).list_for_run(  # type: ignore[arg-type]
        run_id,
        page=4,
        page_size=19,
    )
    total = await ValidationFindingRepository(  # type: ignore[arg-type]
        session
    ).count_for_run(run_id)

    section_sql = _compiled(session.scalars.await_args_list[0].args[0])
    finding_sql = _compiled(session.scalars.await_args_list[1].args[0])
    assert "LIMIT 17 OFFSET 34" in section_sql
    assert "LIMIT 19 OFFSET 57" in finding_sql
    assert (
        "count(validation_findings.id)"
        in _compiled(session.scalar.await_args.args[0]).lower()
    )
    assert total == 73


@pytest.mark.asyncio
async def test_translation_group_repository_counts_structural_completeness() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=_Rows(
                [
                    (True, 2),
                    (False, 1),
                ]
            )
        )
    )
    run_id = uuid4()

    counts = await TranslationGroupRepository(  # type: ignore[arg-type]
        session
    ).count_completeness_for_run(run_id)

    statement = _compiled(session.execute.await_args.args[0])
    assert counts == (2, 1)
    assert "GROUP BY translation_groups.is_complete" in statement
    assert str(run_id) in statement


@pytest.mark.asyncio
async def test_nested_child_counts_are_limited_to_requested_parent_page() -> None:
    session = SimpleNamespace(scalar=AsyncMock(return_value=0))
    run_id = uuid4()

    await DetectedSectionRepository(  # type: ignore[arg-type]
        session
    ).count_language_results_for_run_page(
        run_id,
        page=3,
        page_size=5,
    )
    await TranslationGroupRepository(  # type: ignore[arg-type]
        session
    ).count_members_for_run_page(
        run_id,
        page=2,
        page_size=7,
    )

    section_sql = _compiled(session.scalar.await_args_list[0].args[0])
    group_sql = _compiled(session.scalar.await_args_list[1].args[0])
    assert "section_language_results" in section_sql
    assert "LIMIT 5 OFFSET 10" in section_sql
    assert "translation_group_members" in group_sql
    assert "LIMIT 7 OFFSET 7" in group_sql


def test_run_section_and_finding_endpoints_expose_pagination() -> None:
    for endpoint in (
        list_compliance_sections,
        list_compliance_translation_groups,
        list_compliance_run_findings,
    ):
        parameters = signature(endpoint).parameters
        assert "page" in parameters
        assert "page_size" in parameters


def test_run_findings_openapi_uses_existing_pagination_contract() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/compliance/runs/{run_id}/findings"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert "FindingListResponse" in json.dumps(response_schema)
    assert set(
        schema["components"]["schemas"]["FindingListResponse"]["properties"]
    ) == {
        "items",
        "page",
        "pageSize",
        "totalItems",
        "totalPages",
    }


def test_job_history_openapi_exposes_compliance_status_filter() -> None:
    operation = app.openapi()["paths"]["/api/v1/compliance/jobs"]["get"]
    parameters = {
        parameter["name"]: parameter for parameter in operation["parameters"]
    }

    assert parameters["complianceStatus"]["in"] == "query"
    assert parameters["complianceStatus"]["required"] is False
    assert "ComplianceStatus" in json.dumps(
        parameters["complianceStatus"]["schema"]
    )


@pytest.mark.asyncio
async def test_job_history_compliance_status_filters_count_and_page_query() -> None:
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=2),
        scalars=AsyncMock(return_value=_Rows()),
    )

    _, total = await ComplianceJobRepository(  # type: ignore[arg-type]
        session
    ).list_page(
        compliance_status=ComplianceStatus.COMPLIANT,
        page=2,
        page_size=1,
    )

    count_sql = _compiled(session.scalar.await_args.args[0])
    page_sql = _compiled(session.scalars.await_args.args[0])
    for sql in (count_sql, page_sql):
        assert (
            "JOIN compliance_runs ON compliance_runs.compliance_job_id "
            "= compliance_jobs.id"
        ) in sql
        assert "compliance_runs.compliance_status = 'COMPLIANT'" in sql
    assert "LIMIT 1 OFFSET 1" in page_sql
    assert total == 2


def test_structural_result_schemas_expose_finding_aggregates() -> None:
    assert "finding_count" in DetectedSectionResponse.model_fields
    assert "finding_count" in TranslationGroupResponse.model_fields


@pytest.mark.asyncio
async def test_structural_endpoints_return_pagination_and_forward_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    section_page = DetectedSectionListResponse(
        items=[],
        page=2,
        pageSize=25,
        totalItems=30,
        totalPages=2,
    )
    group_page = TranslationGroupListResponse(
        items=[],
        page=3,
        pageSize=50,
        totalItems=120,
        totalPages=3,
    )
    finding_page = FindingListResponse(
        items=[],
        page=4,
        pageSize=40,
        totalItems=125,
        totalPages=4,
    )
    service = SimpleNamespace(
        list_sections=AsyncMock(return_value=section_page),
        list_translation_groups=AsyncMock(return_value=group_page),
        list_run_findings=AsyncMock(return_value=finding_page),
    )
    monkeypatch.setattr(
        compliance_endpoints,
        "_query_service",
        Mock(return_value=service),
    )
    section_response = await list_compliance_sections(
        run_id=run_id,
        session=SimpleNamespace(),  # type: ignore[arg-type]
        settings=get_settings(),
        user=SimpleNamespace(),  # type: ignore[arg-type]
        metadata=RequestMetadata(ip_address=None, user_agent=None),
        page=2,
        page_size=25,
    )
    section_id = uuid4()
    container_id = uuid4()
    group_response = await list_compliance_translation_groups(
        run_id=run_id,
        session=SimpleNamespace(),  # type: ignore[arg-type]
        settings=get_settings(),
        user=SimpleNamespace(),  # type: ignore[arg-type]
        metadata=RequestMetadata(ip_address=None, user_agent=None),
        container_id=container_id,
        detected_section_id=section_id,
        is_complete=False,
        is_order_valid=False,
        low_confidence=True,
        page=3,
        page_size=50,
    )
    finding_response = await list_compliance_run_findings(
        run_id=run_id,
        session=SimpleNamespace(),  # type: ignore[arg-type]
        settings=get_settings(),
        user=SimpleNamespace(),  # type: ignore[arg-type]
        metadata=RequestMetadata(ip_address=None, user_agent=None),
        page=4,
        page_size=40,
    )

    assert section_response.data == section_page
    assert group_response.data == group_page
    assert finding_response.data == finding_page
    service.list_translation_groups.assert_awaited_once_with(
        run_id,
        container_id=container_id,
        detected_section_id=section_id,
        is_complete=False,
        is_order_valid=False,
        low_confidence=True,
        page=3,
        page_size=50,
    )
    service.list_run_findings.assert_awaited_once_with(
        run_id,
        page=4,
        page_size=40,
    )


@pytest.mark.asyncio
async def test_summary_and_comparison_use_structural_group_completeness() -> None:
    run_id = uuid4()
    document_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        document_id=document_id,
        status="COMPLETED",
        compliance_status="COMPLIANT",
        compliance_score=100,
        required_languages_json=[],
        detected_languages_json=[],
        rule_snapshot_json={},
        metrics_json={
            "validators": {
                "TRANSLATION_GROUPS": {
                    "metrics": {
                        "totalGroups": 2,
                        "evaluatedGroups": 1,
                        "completeGroups": 1,
                        "incompleteGroups": 0,
                        "lowConfidenceGroups": 1,
                    }
                }
            }
        },
        required_sections_json=[],
        detected_sections_json=[],
        missing_sections_json=[],
        total_findings=0,
        open_findings=0,
        critical_findings=0,
        major_findings=0,
        minor_findings=0,
        information_findings=0,
        warnings_json=[],
    )
    user = SimpleNamespace(
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
        department_id=None,
    )
    service = ComplianceQueryService(
        SimpleNamespace(),  # type: ignore[arg-type]
        get_settings(),
        user,  # type: ignore[arg-type]
        RequestMetadata(ip_address=None, user_agent=None),
    )
    service._run = AsyncMock(return_value=run)  # type: ignore[method-assign]
    service.findings = SimpleNamespace(
        count_by_language_for_run=AsyncMock(return_value={}),
    )
    service.groups = SimpleNamespace(
        count_completeness_for_run=AsyncMock(return_value=(2, 0)),
        count_invalid_order_for_run=AsyncMock(return_value=0),
    )

    summary = await service.summary(run_id)

    assert summary.translation_groups.total == 2
    assert summary.translation_groups.complete == 2
    assert summary.translation_groups.incomplete == 0
    assert summary.translation_groups.low_confidence == 1

    previous = SimpleNamespace(
        id=uuid4(),
        document_id=document_id,
        compliance_score=80,
        compliance_status="PARTIALLY_COMPLIANT",
        detected_languages_json=[],
        detected_sections_json=[],
    )
    current = SimpleNamespace(
        id=uuid4(),
        document_id=document_id,
        compliance_score=100,
        compliance_status="COMPLIANT",
        detected_languages_json=[],
        detected_sections_json=[],
    )
    service._run = AsyncMock(  # type: ignore[method-assign]
        side_effect=[current, previous]
    )
    service.findings = SimpleNamespace(
        count_for_run=AsyncMock(return_value=0),
        list_for_run=AsyncMock(),
    )
    service.groups = SimpleNamespace(
        count_completeness_for_run=AsyncMock(
            side_effect=[
                (0, 1),
                (2, 0),
            ]
        )
    )

    comparison = await service.compare(current.id, previous.id)

    assert comparison.translation_group_completeness_change == 2


def test_run_finding_and_translation_group_mappers_redact_source_paths() -> None:
    now = datetime.now(UTC)
    finding = SimpleNamespace(
        id=uuid4(),
        compliance_run_id=uuid4(),
        document_id=uuid4(),
        document_revision_id=uuid4(),
        document_file_id=uuid4(),
        finding_code="MISSING_CHINESE",
        finding_type="LANGUAGE_PRESENCE",
        severity="CRITICAL",
        status="OPEN",
        title="Chinese language is missing",
        language_code="zh",
        detected_section_id=None,
        source_reference=r"C:\private\controlled-source.pdf",
        page_number=1,
        worksheet_name=None,
        cell_coordinate=None,
        assigned_to=None,
        is_system_generated=True,
        is_repeat=False,
        created_at=now,
        updated_at=now,
    )
    mapped_finding = compliance_finding_list_item(finding)
    assert mapped_finding.source_reference == "[redacted source reference]"

    group_id = uuid4()
    member = SimpleNamespace(
        id=uuid4(),
        translation_group_id=group_id,
        language_code="id",
        source_type="NATIVE_EXTRACTION",
        extracted_block_id=uuid4(),
        ocr_block_id=None,
        language_block_result_id=None,
        block_order=1,
        text_snapshot="Controlled multilingual text.",
        confidence=0.99,
        position_json={
            "storagePath": r"C:\private\member-source.pdf",
            "sourceReference": "/srv/private/member-source.pdf",
            "nested": [r"C:\private\nested-source.pdf"],
            "page": 1,
        },
        created_at=now,
    )
    group = SimpleNamespace(
        id=group_id,
        compliance_run_id=uuid4(),
        container_id=None,
        detected_section_id=None,
        group_index=0,
        group_type="PARAGRAPH_GROUP",
        start_block_order=1,
        end_block_order=1,
        source_reference="/srv/private/group-source.pdf",
        expected_languages_json=["id", "en", "zh"],
        detected_languages_json=["id"],
        language_order_json=["id"],
        is_complete=False,
        is_order_valid=True,
        confidence=0.99,
        metrics_json={"sourceReference": r"C:\private\group-metric-source.pdf"},
        members=[member],
        created_at=now,
    )

    mapped_group = translation_group_response(group)
    payload = mapped_group.model_dump(mode="json", by_alias=True)
    serialized = json.dumps(payload)

    assert mapped_group.source_reference == "[redacted source reference]"
    assert payload["metrics"]["sourceReference"] == ("[redacted source reference]")
    assert payload["members"][0]["position"]["sourceReference"] == (
        "[redacted source reference]"
    )
    assert "storagePath" not in payload["members"][0]["position"]
    assert r"C:\private" not in serialized
    assert "/srv/private" not in serialized


@pytest.mark.asyncio
async def test_run_findings_query_returns_counted_bounded_safe_page() -> None:
    run_id = uuid4()
    now = datetime.now(UTC)
    finding = SimpleNamespace(
        id=uuid4(),
        compliance_run_id=run_id,
        document_id=uuid4(),
        document_revision_id=uuid4(),
        document_file_id=uuid4(),
        finding_code="MISSING_CHINESE",
        finding_type="LANGUAGE_PRESENCE",
        severity="CRITICAL",
        status="OPEN",
        title="Chinese language is missing",
        language_code="zh",
        detected_section_id=None,
        source_reference="/srv/private/source.pdf",
        page_number=1,
        worksheet_name=None,
        cell_coordinate=None,
        assigned_to=None,
        is_system_generated=True,
        is_repeat=False,
        created_at=now,
        updated_at=now,
    )
    user = SimpleNamespace(
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
        department_id=None,
    )
    service = ComplianceQueryService(
        SimpleNamespace(),  # type: ignore[arg-type]
        get_settings(),
        user,  # type: ignore[arg-type]
        RequestMetadata(ip_address=None, user_agent=None),
    )
    service._run = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(id=run_id)
    )
    service.findings = SimpleNamespace(
        count_for_run=AsyncMock(return_value=125),
        list_for_run=AsyncMock(return_value=[finding]),
    )

    page = await service.list_run_findings(
        run_id,
        page=4,
        page_size=40,
    )

    assert page.page == 4
    assert page.page_size == 40
    assert page.total_items == 125
    assert page.total_pages == 4
    assert page.items[0].source_reference == "[redacted source reference]"
    service.findings.count_for_run.assert_awaited_once_with(run_id)
    service.findings.list_for_run.assert_awaited_once_with(
        run_id,
        page=4,
        page_size=40,
    )


@pytest.mark.asyncio
async def test_translation_group_page_filters_are_applied_before_limit() -> None:
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=2),
        scalars=AsyncMock(return_value=_Rows()),
    )
    run_id = uuid4()
    section_id = uuid4()
    container_id = uuid4()

    await TranslationGroupRepository(  # type: ignore[arg-type]
        session
    ).list_for_run(
        run_id,
        container_id=container_id,
        detected_section_id=section_id,
        is_complete=False,
        is_order_valid=False,
        low_confidence=True,
        confidence_threshold=0.65,
        page=2,
        page_size=10,
    )

    count_sql = _compiled(session.scalar.await_args.args[0])
    page_sql = _compiled(session.scalars.await_args.args[0])
    for sql in (count_sql, page_sql):
        assert str(container_id) in sql
        assert str(section_id) in sql
        assert "translation_groups.is_complete IS false" in sql
        assert "translation_groups.is_order_valid IS false" in sql
        assert "translation_groups.confidence < 0.65" in sql
    assert "LIMIT 10 OFFSET 10" in page_sql


@pytest.mark.asyncio
async def test_export_rejects_nested_rows_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(
        update={
            "compliance_export_max_rows": 2,
            "compliance_db_batch_size": 1,
        }
    )
    user = SimpleNamespace(
        id=uuid4(),
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
        department_id=None,
    )
    session = SimpleNamespace()
    service = ComplianceResultExportService(
        session,  # type: ignore[arg-type]
        settings,
        user,  # type: ignore[arg-type]
        RequestMetadata(ip_address=None, user_agent=None),
    )
    run = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(service, "_run", AsyncMock(return_value=run))
    service.sections = SimpleNamespace(
        count_for_run=AsyncMock(return_value=2),
        count_language_results_for_run=AsyncMock(return_value=2),
        list_for_run=AsyncMock(),
    )
    service.groups = SimpleNamespace(
        count_for_run=AsyncMock(return_value=1),
        count_members_for_run=AsyncMock(return_value=3),
        list_for_run=AsyncMock(),
    )
    service.findings = SimpleNamespace(
        count_for_run=AsyncMock(return_value=2),
        list_for_run=AsyncMock(),
    )

    with pytest.raises(ApplicationError) as captured:
        await service.export(run.id, export_format="json")

    assert captured.value.errors
    assert captured.value.errors[0].code == "COMPLIANCE_EXPORT_LIMIT_EXCEEDED"
    service.sections.list_for_run.assert_not_awaited()
    service.groups.list_for_run.assert_not_awaited()
    service.findings.list_for_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_loads_more_than_one_hundred_previous_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_findings = [SimpleNamespace(id=uuid4()) for _ in range(125)]
    count_for_run = AsyncMock(return_value=len(previous_findings))
    list_for_run = AsyncMock(return_value=previous_findings)
    monkeypatch.setattr(
        ValidationFindingRepository,
        "count_for_run",
        count_for_run,
    )
    monkeypatch.setattr(
        ValidationFindingRepository,
        "list_for_run",
        list_for_run,
    )
    worker = ComplianceWorkerService(get_settings())
    previous = SimpleNamespace(id=uuid4())

    result = await worker._load_previous_findings(
        SimpleNamespace(),  # type: ignore[arg-type]
        previous,  # type: ignore[arg-type]
    )

    assert len(result) == 125
    list_for_run.assert_awaited_once_with(
        previous.id,
        page=1,
        page_size=125,
    )
