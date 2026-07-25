"""Focused metadata and route-contract tests for Phase 7 language backend."""

from app.api.v1.endpoints.language_detection import router
from app.models.language_block_result import LanguageBlockResult
from app.models.language_container_summary import LanguageContainerSummary
from app.models.language_detection_job import LanguageDetectionJob
from app.models.language_detection_run import LanguageDetectionRun


def test_language_models_define_required_tables_and_constraints() -> None:
    assert LanguageDetectionJob.__tablename__ == "language_detection_jobs"
    assert LanguageDetectionRun.__tablename__ == "language_detection_runs"
    assert LanguageBlockResult.__tablename__ == "language_block_results"
    assert (
        LanguageContainerSummary.__tablename__
        == "language_container_summaries"
    )

    block_constraints = {
        constraint.name
        for constraint in LanguageBlockResult.__table__.constraints
    }
    assert (
        "ck_language_block_results_exactly_one_source_block"
        in block_constraints
    )
    job_indexes = {
        index.name for index in LanguageDetectionJob.__table__.indexes
    }
    assert (
        "uq_language_detection_jobs_one_active_per_file" in job_indexes
    )


def test_language_endpoint_contract_contains_all_required_routes() -> None:
    routes = {
        (method, route.path)
        for route in router.routes
        for method in (route.methods or set())
    }
    expected = {
        ("GET", "/language-detection/documents"),
        ("POST", "/language-detection/jobs"),
        ("GET", "/language-detection/jobs"),
        ("GET", "/language-detection/jobs/{job_id}"),
        ("POST", "/language-detection/jobs/{job_id}/cancel"),
        ("GET", "/language-detection/runs/{run_id}"),
        ("GET", "/language-detection/runs/{run_id}/blocks"),
        ("GET", "/language-detection/runs/{run_id}/containers"),
        ("GET", "/language-detection/runs/{run_id}/summary"),
        ("GET", "/language-detection/runs/{run_id}/export"),
        ("POST", "/language-detection/runs/{run_id}/redetect"),
        ("GET", "/document-files/{file_id}/language-detection"),
        (
            "GET",
            "/document-files/{file_id}/language-detection-history",
        ),
    }
    assert expected.issubset(routes)
