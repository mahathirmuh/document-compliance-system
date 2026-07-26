"""Focused Phase 9 revision-comparison and reporting hardening tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.endpoints import revision_comparisons as revision_endpoints
from app.core.authorization import UserRole
from app.core.exceptions import AuthorizationError
from app.models.glossary_enums import GlossaryValidationStatus
from app.models.report_snapshot import (
    AdvancedReportType,
    ReportFileFormat,
    ReportJobStatus,
    ReportSnapshot,
    ReportSnapshotStatus,
)
from app.models.revision_comparison import (
    RevisionComparisonClassification,
)
from app.models.revision_comparison_job import (
    RevisionComparisonJob,
    RevisionComparisonJobStatus,
    RevisionComparisonJobType,
)
from app.models.similarity_enums import SimilarityRunStatus
from app.models.user import User
from app.repositories.report_snapshot_repository import (
    ReportSnapshotRepository,
)
from app.schemas.advanced_reporting import (
    AdvancedReportFilters,
    AdvancedReportGenerateRequest,
    ReportScheduleCreateRequest,
)
from app.schemas.revision_comparison import (
    RevisionFindingChange,
    RevisionSectionChangesResponse,
)
from app.services.reporting.advanced_reporting_service import (
    report_snapshot_response,
)
from app.services.reporting.report_dataset_service import (
    ReportDataset,
    ReportDatasetService,
)
from app.services.reporting.report_export_service import ReportExportService
from app.services.reporting.report_filter_service import ReportFilterService
from app.services.reporting.report_pdf_service import ReportPdfService
from app.services.reporting.report_schedule_service import (
    CronValidationError,
    validate_cron_expression,
)
from app.services.revision_comparison.revision_alignment_service import (
    AlignedRevisionPair,
    CanonicalRevisionItem,
    RevisionAlignmentService,
)
from app.services.revision_comparison.revision_change_detection_service import (
    RevisionChangeDetectionService,
)
from app.services.revision_comparison.revision_comparison_persistence_service import (
    RevisionComparisonPersistenceService,
)
from app.services.revision_comparison.revision_comparison_worker_service import (
    RevisionComparisonWorkerError,
    RevisionComparisonWorkerService,
)
from app.services.revision_comparison.revision_context_service import (
    RevisionContext,
    RevisionContextService,
)
from app.services.revision_comparison.revision_finding_comparison_service import (
    RevisionFindingComparisonService,
)
from app.services.revision_comparison.revision_language_comparison_service import (
    RevisionLanguageComparisonService,
)
from app.services.revision_comparison.revision_score_comparison_service import (
    RevisionScoreComparisonService,
)

TestSessionFactory = async_sessionmaker[AsyncSession]


@pytest.mark.asyncio
async def test_revision_section_endpoint_uses_non_shadowed_query_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = uuid4()
    expected = RevisionSectionChangesResponse(
        comparison_id=comparison_id,
        items=[],
    )
    section_changes = AsyncMock(return_value=expected)
    service = SimpleNamespace(section_changes=section_changes)
    monkeypatch.setattr(
        revision_endpoints,
        "RevisionComparisonQueryService",
        lambda *_args: service,
    )

    response = await revision_endpoints.get_revision_section_changes(
        comparison_id,
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )

    assert response.data == expected
    section_changes.assert_awaited_once_with(comparison_id)


def _item(
    text: str,
    order: int,
    *,
    section: str | None = "PURPOSE",
    source_reference: str | None = None,
    language: str = "id",
    group_id: UUID | None = None,
) -> CanonicalRevisionItem:
    return CanonicalRevisionItem(
        id=uuid4(),
        text=text,
        order=order,
        entity_type="PARAGRAPH",
        language_code=language,
        source_reference=source_reference,
        section_code=section,
        translation_group_id=group_id,
        translation_group_type="PARAGRAPH_GROUP",
    )


def test_alignment_retains_rewritten_block_with_stable_provenance() -> None:
    base = _item(
        "Old operational wording.",
        0,
        source_reference="word/paragraph/7",
    )
    target = _item(
        "Completely rewritten safety instruction.",
        4,
        source_reference="word/paragraph/7",
    )

    pairs = RevisionAlignmentService(fuzzy_threshold=0.58).align(
        [base], [target]
    )

    assert len(pairs) == 1
    assert pairs[0].base is base
    assert pairs[0].target is target
    assert pairs[0].alignment_confidence >= 0.72
    assert "SOURCE_REFERENCE" in pairs[0].alignment_signals


def test_alignment_index_keeps_far_exact_match_with_bounded_candidates() -> None:
    service = RevisionAlignmentService(
        fuzzy_threshold=0.58,
        maximum_candidates_per_signal=8,
    )
    base = _item("Stable moved paragraph", 0, section=None)
    targets = [
        _item(f"Unrelated paragraph {index}", index, section=None)
        for index in range(200)
    ]
    moved = _item("Stable moved paragraph", 500, section=None)
    targets.append(moved)
    index = service._build_index(targets)
    candidates = service._candidate_indices(
        base, index, set(range(len(targets)))
    )

    assert len(candidates) <= 8 * 5
    assert targets.index(moved) in candidates
    pairs = service.align([base], targets)
    assert pairs[0].target is moved
    assert pairs[0].moved is True


def test_language_comparison_treats_explicit_empty_revision_as_empty() -> None:
    target = _item("English addition", 0, language="en")
    change = RevisionChangeDetectionService().classify(
        AlignedRevisionPair(
            base=None,
            target=target,
            text_similarity=0,
            structural_similarity=0,
            alignment_confidence=1,
        )
    )

    rows = RevisionLanguageComparisonService().summarize(
        [change],
        base_language_counts={},
        target_language_counts={"en": 1},
        base_language_coverage={"en": 0.0},
        target_language_coverage={"en": 24.5},
    )
    english = next(item for item in rows if item["languageCode"] == "en")

    assert english["baseCount"] == 0
    assert english["targetCount"] == 1
    assert english["baseCoverage"] == 0
    assert english["targetCoverage"] == 24.5
    assert english["coverageChange"] == 24.5
    assert english["fixedMissingLanguage"] is True


def test_revision_coverage_prefers_retained_character_metric() -> None:
    run = SimpleNamespace(
        metadata_json={
            "coverage": {
                "blockCoverage": {"id": 50, "en": 25, "zh": 25},
                "characterCoverage": {
                    "id": 60.5,
                    "en": 30.25,
                    "zh": 9.25,
                },
            }
        }
    )

    coverage, basis = RevisionContextService._retained_language_coverage(
        run
    )

    assert basis == "characterCoverage"
    assert coverage == {"id": 60.5, "en": 30.25, "zh": 9.25}


def test_findings_are_candidates_only_and_duplicates_are_retained() -> None:
    repeated = {
        "deduplicationKey": "MISSING_CHINESE|PURPOSE|zh|p1",
        "findingCode": "MISSING_CHINESE",
        "severity": "MAJOR",
        "status": "OPEN",
        "section": "PURPOSE",
        "languageCode": "zh",
        "sourceReference": "p1",
    }
    removed = {
        "deduplicationKey": "MISSING_ENGLISH|SCOPE|en|p2",
        "findingCode": "MISSING_ENGLISH",
        "severity": "MAJOR",
        "status": "OPEN",
    }
    service = RevisionFindingComparisonService()

    results, summary = service.compare(
        [repeated, repeated, removed],
        [repeated, repeated],
    )

    assert len(results) == 3
    assert summary["UNCHANGED"] == 2
    assert summary["NO_LONGER_REPRODUCED"] == 1
    candidate = next(
        item
        for item in results
        if item["comparisonStatus"] == "NO_LONGER_REPRODUCED"
    )
    assert candidate["candidateResolution"] is True
    response = RevisionFindingChange.model_validate(candidate)
    assert response.candidate_resolution is True
    assert removed["status"] == "OPEN"


def test_score_classification_includes_critical_and_glossary_deltas() -> None:
    service = RevisionScoreComparisonService()

    assert (
        service.classify(
            compliance_delta=5,
            similarity_delta=0.05,
            glossary_violation_delta=-2,
            open_finding_delta=-1,
            critical_finding_delta=-1,
        )
        is RevisionComparisonClassification.IMPROVED
    )
    assert (
        service.classify(
            compliance_delta=2,
            similarity_delta=None,
            glossary_violation_delta=1,
            open_finding_delta=0,
        )
        is RevisionComparisonClassification.MIXED
    )


class _ComparisonRepository:
    def __init__(self) -> None:
        self.item = None

    async def add(self, item):
        item.id = item.id or uuid4()
        self.item = item
        return item


class _ChangeRepository:
    def __init__(self) -> None:
        self.items = []

    async def bulk_add(self, items):
        self.items.extend(items)
        return list(items)


@pytest.mark.asyncio
async def test_persistence_counts_sections_and_translation_groups() -> None:
    base_group, target_group = uuid4(), uuid4()
    removed_group, added_group = uuid4(), uuid4()
    base_modified = _item(
        "Old", 0, section="A", group_id=base_group
    )
    target_modified = _item(
        "New", 0, section="A", group_id=target_group
    )
    removed = _item(
        "Removed", 1, section="REMOVED", group_id=removed_group
    )
    added = _item(
        "Added", 1, section="ADDED", group_id=added_group
    )
    pairs = [
        AlignedRevisionPair(
            base=base_modified,
            target=target_modified,
            text_similarity=0.2,
            structural_similarity=1,
            alignment_confidence=0.8,
        ),
        AlignedRevisionPair(
            base=removed,
            target=None,
            text_similarity=0,
            structural_similarity=0,
            alignment_confidence=1,
        ),
        AlignedRevisionPair(
            base=None,
            target=added,
            text_similarity=0,
            structural_similarity=0,
            alignment_confidence=1,
        ),
    ]
    changes = RevisionChangeDetectionService().detect(pairs)
    document_id = uuid4()
    base_revision_id, target_revision_id = uuid4(), uuid4()
    base_file_id, target_file_id = uuid4(), uuid4()
    job = RevisionComparisonJob(
        id=uuid4(),
        document_id=document_id,
        base_revision_id=base_revision_id,
        target_revision_id=target_revision_id,
        base_document_file_id=base_file_id,
        target_document_file_id=target_file_id,
        job_type=RevisionComparisonJobType.INITIAL,
        status=RevisionComparisonJobStatus.PERSISTING,
        requested_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        requested_by=uuid4(),
    )
    base = RevisionContext(
        document_file_id=base_file_id,
        document_revision_id=base_revision_id,
        extraction_run_id=uuid4(),
        compliance_run_id=None,
        similarity_run_id=None,
        glossary_run_id=None,
        content_hash="a" * 64,
        items=[base_modified, removed],
        language_counts={"id": 2},
        compliance_score=70,
        compliance_status="PARTIALLY_COMPLIANT",
        findings=[],
        glossary_violation_count=2,
        open_finding_count=2,
        critical_open_finding_count=1,
    )
    target = RevisionContext(
        document_file_id=target_file_id,
        document_revision_id=target_revision_id,
        extraction_run_id=uuid4(),
        compliance_run_id=None,
        similarity_run_id=None,
        glossary_run_id=None,
        content_hash="b" * 64,
        items=[target_modified, added],
        language_counts={"id": 2},
        compliance_score=80,
        compliance_status="COMPLIANT",
        findings=[],
        glossary_violation_count=1,
        open_finding_count=1,
        critical_open_finding_count=0,
    )
    comparisons = _ComparisonRepository()
    persisted_changes = _ChangeRepository()

    result = await RevisionComparisonPersistenceService(
        comparisons, persisted_changes
    ).persist(
        job=job,
        base=base,
        target=target,
        pairs=pairs,
        detected_changes=changes,
        language_summary=[],
        finding_changes=[],
        finding_summary={},
        classification=RevisionComparisonClassification.IMPROVED,
        warnings=[],
    )

    assert result.total_changes == 3
    assert result.added_sections == 1
    assert result.removed_sections == 1
    assert result.modified_sections == 1
    assert result.added_translation_groups == 1
    assert result.removed_translation_groups == 1
    assert result.modified_translation_groups == 1
    assert result.summary_json["glossaryViolationChange"] == -1
    assert result.summary_json["criticalFindingChange"] == -1
    assert len(persisted_changes.items) == 3


def test_worker_rejects_file_scope_mismatch() -> None:
    document_id = uuid4()
    base_revision_id, target_revision_id = uuid4(), uuid4()
    base_file_id, target_file_id = uuid4(), uuid4()
    job = SimpleNamespace(
        document_id=document_id,
        base_revision_id=base_revision_id,
        target_revision_id=target_revision_id,
        base_document_file_id=base_file_id,
        target_document_file_id=target_file_id,
    )
    base_file = SimpleNamespace(
        id=base_file_id,
        document_id=document_id,
        document_revision_id=base_revision_id,
    )
    wrong_target = SimpleNamespace(
        id=target_file_id,
        document_id=uuid4(),
        document_revision_id=target_revision_id,
    )

    with pytest.raises(
        RevisionComparisonWorkerError,
        match="do not match",
    ):
        RevisionComparisonWorkerService._validate_job_files(
            job, base_file, wrong_target
        )


class _ScalarSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    async def scalars(self, _statement):
        return self.rows


@pytest.mark.asyncio
async def test_reporting_uses_real_similarity_and_glossary_fields() -> None:
    now = datetime.now(UTC)
    similarity = SimpleNamespace(
        id=uuid4(),
        document_id=uuid4(),
        status=SimilarityRunStatus.COMPLETED,
        average_similarity=Decimal("0.80"),
        minimum_similarity=Decimal("0.55"),
        id_en_average_similarity=Decimal("0.81"),
        id_zh_average_similarity=Decimal("0.79"),
        en_zh_average_similarity=Decimal("0.80"),
        low_similarity_groups=2,
        review_similarity_groups=3,
        number_mismatch_count=1,
        date_mismatch_count=2,
        measurement_mismatch_count=3,
        reference_mismatch_count=4,
        negation_mismatch_count=5,
        created_at=now,
    )
    similarity_dataset = await ReportDatasetService(
        _ScalarSession([similarity]),
        maximum_rows=100,
        maximum_chart_categories=20,
    ).build(
        AdvancedReportType.TRANSLATION_SIMILARITY,
        AdvancedReportFilters(),
    )
    assert similarity_dataset.summary["lowSimilarityGroups"] == 2
    assert similarity_dataset.summary["needsReviewGroups"] == 3
    assert similarity_dataset.summary["negationMismatches"] == 5
    assert similarity_dataset.summary["idEnAverageSimilarity"] == 0.81

    glossary = SimpleNamespace(
        id=uuid4(),
        document_id=uuid4(),
        status=GlossaryValidationStatus.COMPLETED,
        total_terms=20,
        matched_terms=10,
        preferred_term_matches=8,
        forbidden_term_matches=2,
        missing_required_translations=3,
        inconsistent_terms=4,
        exception_applied_count=5,
        total_findings=9,
        created_at=now,
    )
    glossary_dataset = await ReportDatasetService(
        _ScalarSession([glossary]),
        maximum_rows=100,
        maximum_chart_categories=20,
    ).build(
        AdvancedReportType.GLOSSARY_COMPLIANCE,
        AdvancedReportFilters(),
    )
    assert glossary_dataset.summary["preferredTermCompliance"] == 80
    assert glossary_dataset.summary["forbiddenMatches"] == 2
    assert glossary_dataset.summary["missingRequiredTranslations"] == 3
    assert glossary_dataset.summary["exceptionsApplied"] == 5


def _user(
    *,
    role: UserRole,
    department_id: UUID | None,
    is_superuser: bool = False,
) -> User:
    return User(
        id=uuid4(),
        name="Report User",
        email=f"{uuid4()}@example.com",
        password_hash="not-used",
        role=role,
        department_id=department_id,
        is_active=True,
        is_superuser=is_superuser,
        failed_login_attempts=0,
    )


def test_report_filters_enforce_department_scope() -> None:
    department_id = uuid4()
    service = ReportFilterService(
        _user(role=UserRole.VIEWER, department_id=department_id)
    )

    assert service.validate(
        AdvancedReportFilters()
    ).department_ids == [department_id]
    with pytest.raises(AuthorizationError):
        service.validate(
            AdvancedReportFilters(department_ids=[uuid4()])
        )
    with pytest.raises(AuthorizationError):
        ReportFilterService(
            _user(role=UserRole.VIEWER, department_id=None)
        ).validate(AdvancedReportFilters())

    cross_department = ReportFilterService(
        _user(
            role=UserRole.DOCUMENT_CONTROLLER,
            department_id=department_id,
        )
    )
    requested = [uuid4(), uuid4()]
    assert cross_department.validate(
        AdvancedReportFilters(department_ids=requested)
    ).department_ids == requested


@pytest.mark.asyncio
async def test_report_snapshot_repository_does_not_expose_global_scope(
    session_factory: TestSessionFactory,
) -> None:
    department_id, other_department_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    own = _snapshot(department_id, now)
    other = _snapshot(
        other_department_id,
        now - timedelta(days=2),
        file_format=ReportFileFormat.PDF,
    )
    global_snapshot = _snapshot(None, now)
    async with session_factory() as session:
        session.add_all([own, other, global_snapshot])
        await session.commit()

    async with session_factory() as session:
        repository = ReportSnapshotRepository(session)
        items, total = await repository.list_page(
            department_ids=[department_id],
            report_types=None,
            statuses=None,
            job_statuses=None,
            page=1,
            page_size=20,
        )
        assert total == 1
        assert [item.id for item in items] == [own.id]
        assert (
            await repository.get_by_id(
                global_snapshot.id,
                department_ids=[department_id],
            )
            is None
        )

        all_items, all_total = await repository.list_page(
            department_ids=None,
            report_types=None,
            statuses=None,
            job_statuses=None,
            page=1,
            page_size=20,
        )
        assert all_total == 3
        assert {item.id for item in all_items} == {
            own.id,
            other.id,
            global_snapshot.id,
        }
        filtered, filtered_total = await repository.list_page(
            department_ids=None,
            report_types=None,
            statuses=None,
            job_statuses=None,
            page=1,
            page_size=20,
            file_formats=[ReportFileFormat.PDF],
            generated_from=now - timedelta(days=3),
            generated_to=now - timedelta(days=1),
        )
        assert filtered_total == 1
        assert [item.id for item in filtered] == [other.id]


def _snapshot(
    department_id: UUID | None,
    now: datetime,
    *,
    file_format: ReportFileFormat = ReportFileFormat.JSON,
) -> ReportSnapshot:
    return ReportSnapshot(
        id=uuid4(),
        report_type=AdvancedReportType.COMPLIANCE_OVERVIEW,
        report_name="Private Report",
        filters_json={},
        status=ReportSnapshotStatus.AVAILABLE,
        job_status=ReportJobStatus.COMPLETED,
        progress=100,
        generated_by=uuid4(),
        scope_department_id=department_id,
        requested_at=now,
        started_at=now,
        generated_at=now,
        file_format=file_format,
        storage_key=(
            f"reports/private/{uuid4()}.{file_format.value}"
        ),
        file_size=100,
        metadata_json={"privacy": {"fullTextIncluded": False}},
        created_at=now,
        updated_at=now,
    )


def test_report_response_hides_storage_and_pdf_text_is_bounded() -> None:
    response = report_snapshot_response(
        _snapshot(uuid4(), datetime.now(UTC))
    ).model_dump(mode="json", by_alias=True)

    assert "storageKey" not in response
    assert "storage_key" not in response
    pdf = ReportPdfService(
        maximum_rows=10, maximum_text_characters=12
    )
    assert pdf._bounded_text("x" * 50) == "x" * 12


def test_advanced_report_json_xlsx_and_pdf_exports() -> None:
    dataset = ReportDataset(
        report_type=AdvancedReportType.COMPLIANCE_OVERVIEW,
        summary={"averageComplianceScore": 88.5},
        data_series=[{"category": "QMS", "score": 88.5}],
        tables={
            "Compliance Runs": [
                {
                    "documentCode": "=unsafe-formula",
                    "score": 88.5,
                    "note": "A bounded operational summary.",
                }
            ]
        },
        warnings=[
            "Automated metrics are review signals, not legal proof."
        ],
    )
    filters = AdvancedReportFilters(departmentIds=[uuid4()])
    exporter = ReportExportService(
        xlsx_maximum_rows=100,
        pdf_maximum_rows=100,
        text_maximum_characters=20,
    )

    json_content = exporter.build(
        dataset,
        report_name="Quality Overview",
        filters=filters,
        output_format=ReportFileFormat.JSON,
    )
    xlsx_content = exporter.build(
        dataset,
        report_name="Quality Overview",
        filters=filters,
        output_format=ReportFileFormat.XLSX,
    )
    pdf_content = exporter.build(
        dataset,
        report_name="Quality Overview",
        filters=filters,
        output_format=ReportFileFormat.PDF,
    )

    assert json_content.startswith(b"{")
    workbook = load_workbook(BytesIO(xlsx_content), data_only=False)
    assert (
        workbook["Compliance Runs"]["A2"].value
        == "'=unsafe-formula"
    )
    assert pdf_content.startswith(b"%PDF")


def test_report_request_and_schedule_validation() -> None:
    with pytest.raises(ValueError, match="visible characters"):
        AdvancedReportGenerateRequest(
            reportType="COMPLIANCE_OVERVIEW",
            reportName="   ",
            outputFormat="json",
        )
    with pytest.raises(ValueError, match="duplicates"):
        ReportScheduleCreateRequest(
            name="Daily",
            reportType="COMPLIANCE_OVERVIEW",
            formats=["json", "json"],
            scheduleType="DAILY",
        )
    assert validate_cron_expression("*/15 0-23 * * 1-5") == (
        "*/15 0-23 * * 1-5"
    )
    with pytest.raises(CronValidationError):
        validate_cron_expression("0 0 * * MON")
    with pytest.raises(CronValidationError):
        validate_cron_expression("60 0 * * *")
