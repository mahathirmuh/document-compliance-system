"""Top-level router for API version 1."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    document_export,
    document_file_links,
    document_files,
    document_import,
    document_revisions,
    documents,
    extraction_runs,
    extractions,
    health,
    language_detection,
    master_data,
    master_data_transfer,
    ocr,
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
