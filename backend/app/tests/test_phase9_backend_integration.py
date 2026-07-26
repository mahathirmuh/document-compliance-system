"""Cross-cutting Phase 9 backend contract and scope regressions."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.authorization import UserRole
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.main import app
from app.models.compliance_enums import (
    FindingCode,
    FindingSeverity,
    FindingStatus,
    FindingType,
)
from app.models.glossary_enums import (
    GlossaryExceptionScopeType,
    GlossaryExceptionType,
    GlossaryLanguageCode,
    GlossaryScopeType,
    GlossaryTermSeverity,
    GlossaryTermType,
)
from app.models.glossary_exception import GlossaryException
from app.models.glossary_profile import GlossaryProfile
from app.models.glossary_term import GlossaryTerm
from app.models.glossary_translation import GlossaryTranslation
from app.models.similarity_enums import (
    ConsistencyStatus,
    SimilarityAnalysisStatus,
    SimilarityCategory,
    SimilarityRunStatus,
)
from app.models.similarity_job import SimilarityJob
from app.models.similarity_result import TranslationSimilarityResult
from app.models.similarity_run import SimilarityRun
from app.models.translation_group_member import TranslationGroupMember
from app.models.user import User
from app.models.validation_finding import ValidationFinding
from app.repositories.similarity_job_repository import (
    SimilarityJobRepository,
)
from app.repositories.similarity_run_repository import (
    SimilarityRunRepository,
)
from app.schemas.glossary import GlossaryTestMatchRequest
from app.services.auth.auth_service import RequestMetadata
from app.services.glossary.glossary_service import GlossaryService
from app.services.similarity.similarity_job_service import (
    SimilarityJobService,
)
from app.services.similarity.similarity_query_service import (
    SimilarityQueryService,
)
from app.workers.celery_app import celery_app
from app.workers.glossary_tasks import process_glossary_validation_job
from app.workers.similarity_tasks import process_similarity_job


def test_phase9_openapi_exposes_review_safe_backend_contracts() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert schema["info"]["version"] == "1.0.0"
    assert {
        "/api/v1/similarity/jobs",
        "/api/v1/similarity/runs/{run_id}/results",
        "/api/v1/glossary/test-match",
        "/api/v1/glossary/validation/jobs",
        "/api/v1/health/dependencies",
    }.issubset(paths)

    result_parameters = {
        item["name"]
        for item in paths[
            "/api/v1/similarity/runs/{run_id}/results"
        ]["get"]["parameters"]
    }
    assert {
        "sectionId",
        "sourceLanguage",
        "targetLanguage",
        "similarityCategory",
        "minimumScore",
        "maximumScore",
        "hasNumberMismatch",
        "hasDateMismatch",
        "hasMeasurementMismatch",
        "hasReferenceMismatch",
        "hasNegationMismatch",
        "findingSeverity",
        "search",
        "page",
        "pageSize",
    }.issubset(result_parameters)

    schemas = schema["components"]["schemas"]
    result_fields = schemas[
        "TranslationSimilarityResultResponse"
    ]["properties"]
    assert {
        "sourceTextSnippet",
        "targetTextSnippet",
        "findingCount",
        "relatedFindingIds",
        "structuralGroupConfidence",
        "ocrConfidence",
    }.issubset(result_fields)
    assert "sourceText" not in result_fields
    assert "targetText" not in result_fields

    match_fields = schemas["GlossaryTestMatchOccurrence"]["properties"]
    assert {
        "exceptionApplied",
        "exceptionId",
        "exceptionType",
    }.issubset(match_fields)

    health_fields = schemas["DependencyHealthData"]["properties"]
    assert {
        "similarityModel",
        "glossaryService",
        "revisionComparisonWorker",
        "reportingWorker",
    }.issubset(health_fields)
    assert not {
        "similarityModelPath",
        "storagePath",
        "embeddingVector",
    }.intersection(health_fields)


def test_similarity_and_glossary_tasks_use_exact_phase9_routes() -> None:
    assert process_similarity_job.name == (
        "app.workers.similarity_tasks.process_similarity_job"
    )
    assert process_glossary_validation_job.name == (
        "app.workers.glossary_tasks.process_glossary_validation_job"
    )
    routes = celery_app.conf.task_routes
    assert routes[process_similarity_job.name]["queue"] == "similarity"
    assert (
        routes[process_glossary_validation_job.name]["queue"]
        == "glossary"
    )


@pytest.mark.asyncio
async def test_similarity_results_return_bounded_snippets_and_findings(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    group_id = uuid4()
    source_member = TranslationGroupMember(
        id=uuid4(),
        translation_group_id=group_id,
        language_code="id",
        source_type="NATIVE_EXTRACTION",
        language_block_result_id=uuid4(),
        block_order=0,
        text_snapshot=(
            "  Teks sumber dengan   spasi berulang "
            + ("dan rincian terkontrol " * 8)
        ),
        confidence=0.95,
    )
    target_member = TranslationGroupMember(
        id=uuid4(),
        translation_group_id=group_id,
        language_code="en",
        source_type="NATIVE_EXTRACTION",
        language_block_result_id=uuid4(),
        block_order=1,
        text_snapshot=(
            "Bounded target evidence "
            + ("with controlled details " * 8)
        ),
        confidence=0.95,
    )
    result = TranslationSimilarityResult(
        similarity_run_id=run_id,
        translation_group_id=group_id,
        source_reference="page:1:block:1",
        source_language_code="id",
        target_language_code="en",
        source_member_id=source_member.id,
        target_member_id=target_member.id,
        source_text_hash="a" * 64,
        target_text_hash="b" * 64,
        similarity_score=0.42,
        similarity_category=SimilarityCategory.LOW,
        confidence=0.91,
        analysis_status=SimilarityAnalysisStatus.COMPLETED,
        source_character_count=len(source_member.text_snapshot),
        target_character_count=len(target_member.text_snapshot),
        length_ratio=1.0,
        number_consistency_status=ConsistencyStatus.MATCH,
        date_consistency_status=ConsistencyStatus.NOT_APPLICABLE,
        measurement_consistency_status=ConsistencyStatus.NOT_APPLICABLE,
        reference_consistency_status=ConsistencyStatus.NOT_APPLICABLE,
        negation_consistency_status=ConsistencyStatus.NOT_APPLICABLE,
        metrics_json={
            "groupConfidence": 0.87,
            "ocrConfidence": 0.74,
        },
    )
    finding = ValidationFinding(
        similarity_run_id=run_id,
        document_id=uuid4(),
        document_revision_id=uuid4(),
        document_file_id=uuid4(),
        finding_code=FindingCode.LOW_TRANSLATION_SIMILARITY,
        finding_type=FindingType.TRANSLATION_SIMILARITY,
        severity=FindingSeverity.MAJOR,
        status=FindingStatus.OPEN,
        title="Low translation similarity",
        description="Human review is required.",
        translation_group_id=group_id,
        source_reference=result.source_reference,
    )
    async with session_factory() as session:
        session.add_all(
            (source_member, target_member, result, finding)
        )
        await session.commit()
        await session.refresh(finding)

        service = SimilarityQueryService(
            session,
            cast(
                Settings,
                SimpleNamespace(similarity_snippet_max_characters=50),
            ),
            cast(User, SimpleNamespace()),
            RequestMetadata(ip_address=None, user_agent="pytest"),
        )
        monkeypatch.setattr(
            service,
            "_run",
            AsyncMock(return_value=SimpleNamespace(id=run_id)),
        )
        response = await service.list_results(
            run_id,
            section_id=None,
            source_language=None,
            target_language=None,
            similarity_category=None,
            minimum_score=None,
            maximum_score=None,
            has_number_mismatch=None,
            has_date_mismatch=None,
            has_measurement_mismatch=None,
            has_reference_mismatch=None,
            has_negation_mismatch=None,
            finding_severity=FindingSeverity.MAJOR,
            search="bounded target",
            page=1,
            page_size=100,
        )
        assert response.total_items == 1
        item = response.items[0]
        assert item.finding_count == 1
        assert item.related_finding_ids == [finding.id]
        assert item.structural_group_confidence == pytest.approx(0.87)
        assert item.ocr_confidence == pytest.approx(0.74)
        assert item.source_text_snippet is not None
        assert item.target_text_snippet is not None
        assert len(item.source_text_snippet) <= 50
        assert len(item.target_text_snippet) <= 50
        assert item.source_text_snippet.endswith("…")
        assert item.target_text_snippet.endswith("…")
        assert "  " not in item.source_text_snippet

        no_minor = await service.list_results(
            run_id,
            section_id=None,
            source_language=None,
            target_language=None,
            similarity_category=None,
            minimum_score=None,
            maximum_score=None,
            has_number_mismatch=None,
            has_date_mismatch=None,
            has_measurement_mismatch=None,
            has_reference_mismatch=None,
            has_negation_mismatch=None,
            finding_severity=FindingSeverity.MINOR,
            search=None,
            page=1,
            page_size=100,
        )
        assert no_minor.total_items == 0
        assert no_minor.items == []


def test_similarity_services_enforce_department_scope() -> None:
    own_department_id = uuid4()
    other_department_id = uuid4()
    session = cast(AsyncSession, SimpleNamespace())
    settings = cast(Settings, SimpleNamespace())
    metadata = RequestMetadata(ip_address=None, user_agent="pytest")
    department_user = cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            role=UserRole.DEPARTMENT_USER,
            department_id=own_department_id,
            is_superuser=False,
        ),
    )
    queries = SimilarityQueryService(
        session,
        settings,
        department_user,
        metadata,
    )
    assert queries._scope_department_ids() == [own_department_id]

    jobs = SimilarityJobService(
        session,
        settings,
        department_user,
        metadata,
    )
    assert jobs._scope_department_ids(own_department_id) == [
        own_department_id
    ]
    with pytest.raises(AuthorizationError):
        jobs._scope_department_ids(other_department_id)

    no_department = cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            role=UserRole.VIEWER,
            department_id=None,
            is_superuser=False,
        ),
    )
    with pytest.raises(AuthorizationError):
        SimilarityQueryService(
            session,
            settings,
            no_department,
            metadata,
        )._scope_department_ids()

    cross_department = cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            role=UserRole.DOCUMENT_CONTROLLER,
            department_id=None,
            is_superuser=False,
        ),
    )
    assert (
        SimilarityQueryService(
            session,
            settings,
            cross_department,
            metadata,
        )._scope_department_ids()
        is None
    )


@pytest.mark.asyncio
async def test_failed_similarity_run_is_never_reused(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    document_id = uuid4()
    revision_id = uuid4()
    file_id = uuid4()
    compliance_id = uuid4()
    language_id = uuid4()
    source_hash = "c" * 64
    async with session_factory() as session:
        job = SimilarityJob(
            document_id=document_id,
            document_revision_id=revision_id,
            document_file_id=file_id,
            compliance_run_id=compliance_id,
            language_detection_run_id=language_id,
            source_content_hash=source_hash,
            provider="deterministic",
            model_name="local-test-model",
        )
        await SimilarityJobRepository(session).add(job)
        run = SimilarityRun(
            similarity_job_id=job.id,
            document_id=document_id,
            document_revision_id=revision_id,
            document_file_id=file_id,
            compliance_run_id=compliance_id,
            language_detection_run_id=language_id,
            provider="deterministic",
            model_name="local-test-model",
            status=SimilarityRunStatus.FAILED,
            source_content_hash=source_hash,
        )
        await SimilarityRunRepository(session).add(run)
        await session.commit()

        repository = SimilarityRunRepository(session)
        assert (
            await repository.find_equivalent(
                document_file_id=file_id,
                compliance_run_id=compliance_id,
                source_content_hash=source_hash,
                provider="deterministic",
                model_name="local-test-model",
            )
            is None
        )

        run.status = SimilarityRunStatus.COMPLETED
        await session.commit()
        reusable = await repository.find_equivalent(
            document_file_id=file_id,
            compliance_run_id=compliance_id,
            source_content_hash=source_hash,
            provider="deterministic",
            model_name="local-test-model",
        )
        assert reusable is not None
        assert reusable.id == run.id


@pytest.mark.asyncio
async def test_glossary_match_defaults_to_own_department_and_indicates_exception(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    own_department_id = uuid4()
    other_department_id = uuid4()
    own_profile, own_term = _profile_with_english_term(
        department_id=own_department_id,
        code="OWN_MATCH",
        term_code="CONTROLLED_TERM",
        text="Controlled Term",
    )
    other_profile, _ = _profile_with_english_term(
        department_id=other_department_id,
        code="OTHER_MATCH",
        term_code="FOREIGN_TERM",
        text="Foreign Secret Phrase",
    )
    exception = GlossaryException(
        glossary_term_id=own_term.id,
        scope_type=GlossaryExceptionScopeType.DEPARTMENT,
        department_id=own_department_id,
        exception_type=GlossaryExceptionType.IGNORE_TERM,
        reason="Approved for this department's test context.",
    )
    own_term.exceptions.append(exception)
    user = cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            role=UserRole.VIEWER,
            department_id=own_department_id,
            is_superuser=False,
        ),
    )
    metadata = RequestMetadata(ip_address=None, user_agent="pytest")
    async with session_factory() as session:
        session.add_all((own_profile, other_profile))
        await session.commit()
        await session.refresh(exception)

        service = GlossaryService(session, user, metadata)
        request = GlossaryTestMatchRequest(
            text="Controlled Term and Foreign Secret Phrase",
            languageCode="en",
            profileIds=[own_profile.id, own_profile.id],
        )
        assert request.profile_ids == [own_profile.id]
        response = await service.test_match(
            request.model_copy(update={"profile_ids": []})
        )
        assert response.profile_ids == [own_profile.id]
        assert response.total_matches == 1
        occurrence = response.matches[0]
        assert occurrence.term_code == "CONTROLLED_TERM"
        assert occurrence.exception_applied
        assert occurrence.exception_id == exception.id
        assert (
            occurrence.exception_type
            is GlossaryExceptionType.IGNORE_TERM
        )

        with pytest.raises(AuthorizationError):
            await service.test_match(
                GlossaryTestMatchRequest(
                    text="Foreign Secret Phrase",
                    languageCode=GlossaryLanguageCode.ENGLISH,
                    departmentId=other_department_id,
                )
            )


def _profile_with_english_term(
    *,
    department_id: UUID,
    code: str,
    term_code: str,
    text: str,
) -> tuple[GlossaryProfile, GlossaryTerm]:
    profile = GlossaryProfile(
        id=uuid4(),
        code=code,
        name=f"{code} profile",
        scope_type=GlossaryScopeType.DEPARTMENT,
        department_id=department_id,
        is_default=True,
        is_active=True,
    )
    term = GlossaryTerm(
        id=uuid4(),
        term_code=term_code,
        concept_name=text,
        term_type=GlossaryTermType.PREFERRED,
        severity=GlossaryTermSeverity.MINOR,
        is_active=True,
    )
    term.translations = [
        GlossaryTranslation(
            id=uuid4(),
            language_code=GlossaryLanguageCode.ENGLISH,
            term_text=text,
            normalised_term=text.casefold(),
            is_preferred=True,
            is_required=True,
            is_active=True,
        )
    ]
    profile.terms = [term]
    return profile, term
