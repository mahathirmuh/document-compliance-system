"""Top-level router for API version 1."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_notifications,
    advanced_reports,
    auth,
    compliance,
    compliance_reports,
    dead_letter,
    document_export,
    document_file_links,
    document_files,
    document_import,
    document_revisions,
    documents,
    extraction_runs,
    extractions,
    findings,
    glossary,
    graph_subscriptions,
    health,
    language_detection,
    master_data,
    master_data_transfer,
    microsoft_graph_webhook,
    notifications,
    ocr,
    retention,
    revision_comparisons,
    section_definitions,
    sharepoint_conflicts,
    sharepoint_files,
    sharepoint_integrations,
    sharepoint_sync,
    similarity,
    system_health,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(
    extractions.router,
    prefix="/extractions",
    tags=["Document Extraction"],
)
api_router.include_router(
    extraction_runs.router,
    tags=["Extracted Content"],
)
api_router.include_router(ocr.router, tags=["Document OCR"])
api_router.include_router(compliance.router, tags=["Compliance"])
api_router.include_router(similarity.router, tags=["Translation Similarity"])
api_router.include_router(glossary.router, tags=["Glossary"])
api_router.include_router(
    revision_comparisons.router,
    tags=["Revision Comparisons"],
)
api_router.include_router(advanced_reports.router)
api_router.include_router(
    compliance_reports.router,
    tags=["Compliance Reports"],
)
api_router.include_router(
    findings.router,
    prefix="/findings",
    tags=["Compliance Findings"],
)
api_router.include_router(
    language_detection.router,
    tags=["Language Detection"],
)
api_router.include_router(
    document_files.router,
    prefix="/document-files",
    tags=["Document Files"],
)
api_router.include_router(
    document_import.router,
    prefix="/documents",
    tags=["Document Register Import"],
)
api_router.include_router(
    document_export.router,
    prefix="/documents",
    tags=["Document Register Export"],
)
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Document Register"],
)
api_router.include_router(
    document_revisions.router,
    prefix="/documents",
    tags=["Document Revisions"],
)
api_router.include_router(
    document_file_links.router,
    prefix="/documents",
    tags=["Document Files"],
)
api_router.include_router(
    master_data.router,
    prefix="/master-data",
    tags=["Master Data"],
)
api_router.include_router(
    master_data_transfer.router,
    prefix="/master-data",
    tags=["Master Data Import/Export"],
)
api_router.include_router(
    section_definitions.router,
    prefix="/master-data",
    tags=["Section Definitions"],
)
api_router.include_router(sharepoint_integrations.router)
api_router.include_router(graph_subscriptions.router)
api_router.include_router(sharepoint_sync.router)
api_router.include_router(sharepoint_conflicts.router)
api_router.include_router(sharepoint_files.router)
api_router.include_router(microsoft_graph_webhook.router)
api_router.include_router(notifications.router)
api_router.include_router(admin_notifications.router)
api_router.include_router(retention.router)
api_router.include_router(dead_letter.router)
api_router.include_router(system_health.router)
