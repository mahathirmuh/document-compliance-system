"""Environment-backed application configuration."""

import base64
import binascii
import json
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Literal, Self
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AliasChoices,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or local env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Document Compliance & Multilingual Validation System"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV"),
    )
    backend_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    public_app_url: str = "http://localhost:5173"
    api_base_url: str = "http://localhost:8000"
    database_url: SecretStr | None = None
    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "document_compliance"
    postgres_user: str = "document_compliance"
    postgres_password: SecretStr | None = None
    database_echo: bool = False
    db_pool_size: int = Field(default=20, ge=1, le=200)
    db_max_overflow: int = Field(default=20, ge=0, le=500)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86_400)
    db_statement_timeout_ms: int = Field(default=120_000, ge=1000, le=3_600_000)
    db_connect_timeout_seconds: int = Field(default=10, ge=1, le=120)
    cors_origins: str = Field(
        default='["http://localhost:5173"]',
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS"),
    )
    cors_allow_credentials: bool = True
    trusted_hosts: str = "localhost,127.0.0.1,testserver,test"
    trusted_proxy_ips: str = ""
    forwarded_allow_ips: str = ""
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1, le=365)
    max_login_attempts: int = Field(default=5, ge=1, le=100)
    account_lock_minutes: int = Field(default=15, ge=1, le=1440)
    default_admin_name: str = Field(default="System Administrator", min_length=1)
    default_admin_email: EmailStr = "admin@example.com"
    default_admin_password: SecretStr | None = None
    master_data_import_max_rows: int = Field(default=5000, ge=1, le=100_000)
    master_data_export_max_rows: int = Field(
        default=50_000,
        ge=1,
        le=1_000_000,
    )
    default_company_code: str = Field(
        default="MTI",
        min_length=1,
        max_length=20,
    )
    document_register_import_max_rows: int = Field(
        default=10_000,
        ge=1,
        le=100_000,
    )
    document_register_export_max_rows: int = Field(
        default=100_000,
        ge=1,
        le=1_000_000,
    )
    document_import_max_file_size_mb: int = Field(
        default=25,
        ge=1,
        le=500,
    )
    document_number_max_length: int = Field(default=50, ge=1, le=50)
    document_title_max_length: int = Field(default=500, ge=1, le=500)
    archive_reason_max_length: int = Field(default=1000, ge=1, le=1000)
    application_timezone: str = Field(
        default="Asia/Makassar",
        validation_alias=AliasChoices("APP_TIMEZONE"),
    )
    storage_provider: Literal["local", "sharepoint", "hybrid"] = "local"
    storage_root: Path = Path("storage")
    storage_documents_prefix: str = "documents/originals"
    storage_temp_prefix: str = "documents/temporary"
    storage_quarantine_prefix: str = "documents/quarantine"
    storage_deleted_prefix: str = "documents/deleted"
    document_max_file_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        validation_alias=AliasChoices(
            "DOCUMENT_MAX_FILE_SIZE_MB",
            "MAX_FILE_SIZE_MB",
        ),
    )
    document_batch_max_files: int = Field(default=50, ge=1, le=500)
    document_batch_max_total_size_mb: int = Field(
        default=500,
        ge=1,
        le=5000,
    )
    allowed_document_extensions: str = ".pdf,.docx,.xlsx"
    enable_file_signature_validation: bool = True
    enable_duplicate_file_hash_check: bool = True
    enable_file_quarantine: bool = True
    file_download_chunk_size_kb: int = Field(
        default=1024,
        ge=64,
        le=16_384,
    )
    temp_file_retention_hours: int = Field(default=24, ge=1, le=720)
    ooxml_max_entries: int = Field(default=10_000, ge=10, le=100_000)
    ooxml_max_uncompressed_size_mb: int = Field(
        default=500,
        ge=1,
        le=5000,
    )
    ooxml_max_compression_ratio: float = Field(
        default=1000.0,
        ge=1.0,
        le=100_000.0,
    )
    redis_host: str = Field(default="redis", min_length=1, max_length=255)
    redis_port: int = Field(default=6379, ge=1, le=65_535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: SecretStr | None = None
    redis_ssl: bool = False
    redis_socket_timeout_seconds: int = Field(default=5, ge=1, le=120)
    redis_socket_connect_timeout_seconds: int = Field(default=5, ge=1, le=120)
    redis_health_check_interval_seconds: int = Field(default=30, ge=1, le=300)
    redis_max_connections: int = Field(default=100, ge=1, le=10_000)
    redis_key_prefix: str = "document-compliance:development"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    extraction_queue_name: str = Field(
        default="extraction",
        min_length=1,
        max_length=100,
    )
    extraction_max_file_size_mb: int = Field(default=50, ge=1, le=500)
    extraction_task_time_limit_seconds: int = Field(
        default=1800,
        ge=60,
        le=86_400,
    )
    extraction_task_soft_time_limit_seconds: int = Field(
        default=1500,
        ge=30,
        le=86_399,
    )
    extraction_max_retries: int = Field(default=2, ge=0, le=10)
    extraction_db_batch_size: int = Field(default=1000, ge=1, le=10_000)
    pdf_max_pages: int = Field(default=5000, ge=1, le=100_000)
    pdf_min_characters_per_page: int = Field(default=20, ge=0, le=100_000)
    pdf_scanned_page_ratio_threshold: float = Field(
        default=0.7,
        gt=0.0,
        le=1.0,
    )
    docx_max_paragraphs: int = Field(
        default=500_000,
        ge=1,
        le=5_000_000,
    )
    docx_max_tables: int = Field(default=10_000, ge=1, le=100_000)
    docx_max_table_cells: int = Field(
        default=2_000_000,
        ge=1,
        le=20_000_000,
    )
    xlsx_max_worksheets: int = Field(default=200, ge=1, le=10_000)
    xlsx_max_rows_per_sheet: int = Field(
        default=200_000,
        ge=1,
        le=1_048_576,
    )
    xlsx_max_cells_per_workbook: int = Field(
        default=2_000_000,
        ge=1,
        le=20_000_000,
    )
    xlsx_max_formulas: int = Field(
        default=500_000,
        ge=0,
        le=10_000_000,
    )
    extraction_export_max_blocks: int = Field(
        default=2_000_000,
        ge=1,
        le=20_000_000,
    )
    extraction_search_max_results: int = Field(
        default=500,
        ge=1,
        le=5000,
    )
    ocr_queue_name: str = Field(default="ocr", min_length=1, max_length=100)
    language_queue_name: str = Field(
        default="language",
        min_length=1,
        max_length=100,
    )
    ocr_worker_concurrency: int = Field(default=1, ge=1, le=8)
    language_worker_concurrency: int = Field(default=2, ge=1, le=32)
    ocr_provider: Literal["paddleocr"] = "paddleocr"
    ocr_model_root: Path = Path("models/ocr")
    ocr_render_dpi: int = Field(default=300, ge=72, le=600)
    ocr_render_format: Literal["png"] = "png"
    ocr_max_render_width: int = Field(default=6000, ge=256, le=20_000)
    ocr_max_render_height: int = Field(default=6000, ge=256, le=20_000)
    ocr_max_pages_per_job: int = Field(default=500, ge=1, le=10_000)
    ocr_max_concurrent_jobs_per_user: int = Field(
        default=3,
        ge=1,
        le=100,
    )
    ocr_task_time_limit_seconds: int = Field(
        default=3600,
        ge=60,
        le=86_400,
    )
    ocr_task_soft_time_limit_seconds: int = Field(
        default=3300,
        ge=30,
        le=86_399,
    )
    ocr_max_retries: int = Field(default=1, ge=0, le=10)
    ocr_low_confidence_threshold: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
    )
    ocr_review_confidence_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
    )
    ocr_skip_pages_with_selectable_text: bool = True
    ocr_selectable_text_min_characters: int = Field(
        default=50,
        ge=0,
        le=100_000,
    )
    ocr_temp_image_retention_hours: int = Field(
        default=2,
        ge=1,
        le=168,
    )
    ocr_default_preprocessing_profile: Literal[
        "NONE",
        "STANDARD",
        "AGGRESSIVE",
    ] = "STANDARD"
    ocr_latin_model_name: str = Field(
        default="latin_PP-OCRv5_mobile_rec",
        min_length=1,
        max_length=200,
    )
    ocr_chinese_model_name: str = Field(
        default="PP-OCRv5_mobile_rec",
        min_length=1,
        max_length=200,
    )
    ocr_auto_multilingual_chinese_pass: bool = True
    ocr_auto_multilingual_chinese_pass_confidence_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
    )
    ocr_auto_multilingual_chinese_pass_minimum_characters: int = Field(
        default=20,
        ge=0,
        le=100_000,
    )
    language_model_path: Path = Path("models/language/lid.176.bin")
    language_model_url: str = (
        "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
    )
    language_model_sha256: str | None = None
    language_min_characters: int = Field(default=4, ge=1, le=10_000)
    language_min_alpha_characters: int = Field(
        default=3,
        ge=1,
        le=10_000,
    )
    language_short_text_threshold: int = Field(
        default=20,
        ge=1,
        le=100_000,
    )
    language_confidence_minimum: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
    )
    language_confidence_review_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
    )
    language_han_character_ratio_threshold: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
    )
    language_mixed_secondary_score_threshold: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
    )
    language_mixed_min_character_ratio: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
    )
    language_presence_min_blocks: int = Field(default=2, ge=1, le=100_000)
    language_presence_min_characters: int = Field(
        default=20,
        ge=1,
        le=10_000_000,
    )
    language_detection_db_batch_size: int = Field(
        default=1000,
        ge=1,
        le=10_000,
    )
    language_detection_max_blocks: int = Field(
        default=2_000_000,
        ge=1,
        le=20_000_000,
    )
    language_export_max_blocks: int = Field(
        default=2_000_000,
        ge=1,
        le=20_000_000,
    )
    language_task_time_limit_seconds: int = Field(
        default=1800,
        ge=60,
        le=86_400,
    )
    language_task_soft_time_limit_seconds: int = Field(
        default=1500,
        ge=30,
        le=86_399,
    )
    language_max_retries: int = Field(default=1, ge=0, le=10)
    compliance_queue_name: str = Field(
        default="compliance",
        min_length=1,
        max_length=100,
    )
    compliance_max_blocks: int = Field(
        default=2_000_000,
        ge=1,
        le=10_000_000,
    )
    compliance_max_translation_groups: int = Field(
        default=500_000,
        ge=1,
        le=5_000_000,
    )
    compliance_db_batch_size: int = Field(
        default=1000,
        ge=1,
        le=10_000,
    )
    compliance_task_time_limit_seconds: int = Field(
        default=1800,
        ge=60,
        le=86_400,
    )
    compliance_task_soft_time_limit_seconds: int = Field(
        default=1500,
        ge=30,
        le=86_399,
    )
    compliance_max_retries: int = Field(default=1, ge=0, le=10)
    section_match_min_confidence: float = Field(
        default=0.80,
        ge=0,
        le=1,
    )
    section_fuzzy_match_threshold: float = Field(
        default=0.88,
        ge=0,
        le=1,
    )
    section_heading_max_characters: int = Field(
        default=200,
        ge=1,
        le=10_000,
    )
    section_alias_regex_max_length: int = Field(
        default=500,
        ge=1,
        le=5000,
    )
    section_alias_regex_timeout_ms: int = Field(
        default=100,
        ge=1,
        le=10_000,
    )
    translation_group_max_block_distance: int = Field(
        default=3,
        ge=0,
        le=100,
    )
    translation_group_max_vertical_gap: float = Field(
        default=120,
        ge=0,
        le=100_000,
    )
    translation_group_min_confidence: float = Field(
        default=0.65,
        ge=0,
        le=1,
    )
    finding_export_max_rows: int = Field(
        default=200_000,
        ge=1,
        le=1_000_000,
    )
    compliance_export_max_rows: int = Field(
        default=200_000,
        ge=1,
        le=1_000_000,
    )
    finding_bulk_action_max_items: int = Field(
        default=100,
        ge=1,
        le=10_000,
    )
    similarity_queue_name: str = Field(
        default="similarity", min_length=1, max_length=100
    )
    similarity_provider: Literal["sentence_transformer"] = "sentence_transformer"
    similarity_model_name: str = Field(
        default=("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
        min_length=1,
        max_length=500,
    )
    similarity_model_path: Path = Path("models/similarity")
    similarity_device: Literal["cpu", "cuda", "mps"] = "cpu"
    similarity_batch_size: int = Field(default=32, ge=1, le=1024)
    similarity_max_sequence_length: int = Field(default=512, ge=8, le=8192)
    similarity_normalize_embeddings: bool = True
    similarity_skip_code_like_text: bool = True
    similarity_skip_numeric_only_text: bool = True
    similarity_high_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    similarity_acceptable_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    similarity_review_threshold: float = Field(default=0.58, ge=0.0, le=1.0)
    similarity_critical_low_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    similarity_min_characters_per_text: int = Field(default=10, ge=1, le=100_000)
    similarity_min_group_confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    similarity_text_max_characters: int = Field(default=12_000, ge=10, le=10_000_000)
    similarity_snippet_max_characters: int = Field(
        default=500,
        ge=50,
        le=5000,
    )
    similarity_chunk_max_characters: int = Field(default=1500, ge=10, le=1_000_000)
    similarity_chunk_overlap_characters: int = Field(default=150, ge=0, le=100_000)
    similarity_max_chunks_per_text: int = Field(default=50, ge=1, le=10_000)
    similarity_task_time_limit_seconds: int = Field(default=3600, ge=60, le=86_400)
    similarity_task_soft_time_limit_seconds: int = Field(default=3300, ge=30, le=86_399)
    similarity_max_retries: int = Field(default=1, ge=0, le=10)
    similarity_db_batch_size: int = Field(default=500, ge=1, le=10_000)
    glossary_queue_name: str = Field(default="glossary", min_length=1, max_length=100)
    glossary_term_max_length: int = Field(default=500, ge=1, le=10_000)
    glossary_regex_max_length: int = Field(default=500, ge=1, le=5000)
    glossary_regex_timeout_ms: int = Field(default=100, ge=1, le=10_000)
    glossary_import_max_rows: int = Field(default=100_000, ge=1, le=1_000_000)
    glossary_validation_max_blocks: int = Field(default=2_000_000, ge=1, le=20_000_000)
    glossary_db_batch_size: int = Field(default=1000, ge=1, le=10_000)
    glossary_task_time_limit_seconds: int = Field(default=3600, ge=60, le=86_400)
    glossary_task_soft_time_limit_seconds: int = Field(default=3300, ge=30, le=86_399)
    glossary_max_retries: int = Field(default=1, ge=0, le=10)
    revision_comparison_queue_name: str = Field(
        default="revision-comparison", min_length=1, max_length=100
    )
    revision_comparison_max_blocks: int = Field(default=3_000_000, ge=1, le=20_000_000)
    revision_comparison_max_changes: int = Field(default=1_000_000, ge=1, le=10_000_000)
    revision_comparison_task_time_limit_seconds: int = Field(
        default=3600, ge=60, le=86_400
    )
    revision_comparison_task_soft_time_limit_seconds: int = Field(
        default=3300, ge=30, le=86_399
    )
    revision_comparison_db_batch_size: int = Field(default=1000, ge=1, le=10_000)
    revision_comparison_max_retries: int = Field(default=1, ge=0, le=10)
    revision_alignment_fuzzy_threshold: float = Field(default=0.58, ge=0.0, le=1.0)
    reporting_queue_name: str = Field(default="reporting", min_length=1, max_length=100)
    report_export_max_rows: int = Field(default=500_000, ge=1, le=5_000_000)
    report_snapshot_retention_days: int = Field(default=30, ge=1, le=3650)
    reporting_task_time_limit_seconds: int = Field(
        default=3600,
        ge=60,
        le=86_400,
        validation_alias=AliasChoices(
            "REPORT_TASK_TIME_LIMIT_SECONDS",
            "REPORTING_TASK_TIME_LIMIT_SECONDS",
        ),
    )
    reporting_task_soft_time_limit_seconds: int = Field(default=3300, ge=30, le=86_399)
    reporting_max_retries: int = Field(default=1, ge=0, le=10)
    report_pdf_max_table_rows: int = Field(default=5000, ge=1, le=100_000)
    report_xlsx_max_rows_per_sheet: int = Field(default=1_000_000, ge=1, le=1_048_576)
    report_chart_max_categories: int = Field(default=50, ge=1, le=1000)
    report_text_snippet_max_characters: int = Field(default=500, ge=1, le=10_000)
    report_include_full_text: bool = False
    microsoft_graph_enabled: bool = False
    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: SecretStr | None = None
    microsoft_client_certificate_path: Path | None = None
    microsoft_client_certificate_password: SecretStr | None = None
    microsoft_graph_auth_mode: Literal["client_secret", "certificate"] = "client_secret"
    microsoft_graph_base_url: str = "https://graph.microsoft.com/v1.0"
    microsoft_graph_timeout_seconds: int = Field(default=60, ge=1, le=600)
    microsoft_graph_max_retries: int = Field(default=5, ge=0, le=10)
    microsoft_graph_retry_base_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    microsoft_graph_retry_max_seconds: float = Field(default=120.0, ge=1.0, le=600.0)
    microsoft_graph_token_cache_ttl_seconds: int = Field(default=3000, ge=60, le=86_400)
    sharepoint_site_hostname: str | None = None
    sharepoint_site_path: str | None = None
    sharepoint_site_id: str | None = None
    sharepoint_drive_id: str | None = None
    sharepoint_library_name: str | None = None
    sharepoint_root_folder_path: str = "DocumentCompliance"
    sharepoint_simple_upload_max_mb: int = Field(default=4, ge=1, le=250)
    sharepoint_upload_chunk_size_mb: int = Field(default=10, ge=1, le=60)
    sharepoint_upload_session_expiry_buffer_minutes: int = Field(
        default=10, ge=1, le=120
    )
    sharepoint_upload_max_file_size_mb: int = Field(default=10_240, ge=1, le=250_000)
    sharepoint_sync_enabled: bool = False
    sharepoint_sync_mode: Literal["MANUAL", "SCHEDULED", "WEBHOOK", "HYBRID"] = "MANUAL"
    sharepoint_sync_interval_minutes: int = Field(default=15, ge=1, le=10_080)
    sharepoint_delta_sync_enabled: bool = True
    sharepoint_webhook_enabled: bool = False
    sharepoint_webhook_notification_url: str | None = None
    sharepoint_webhook_client_state: SecretStr | None = None
    sharepoint_webhook_renewal_hours: int = Field(default=24, ge=1, le=168)
    sharepoint_worker_concurrency: int = Field(default=4, ge=1, le=32)
    sharepoint_queue_name: str = Field(
        default="sharepoint", min_length=1, max_length=100
    )
    notification_queue_name: str = Field(
        default="notifications", min_length=1, max_length=100
    )
    maintenance_queue_name: str = Field(
        default="maintenance", min_length=1, max_length=100
    )
    sharepoint_task_time_limit_seconds: int = Field(default=7200, ge=60, le=86_400)
    sharepoint_task_soft_time_limit_seconds: int = Field(default=6900, ge=30, le=86_399)
    sharepoint_max_retries: int = Field(default=3, ge=0, le=10)
    notification_task_time_limit_seconds: int = Field(default=600, ge=30, le=7200)
    notification_task_soft_time_limit_seconds: int = Field(default=540, ge=10, le=7199)
    notification_max_retries: int = Field(default=3, ge=0, le=10)
    maintenance_task_time_limit_seconds: int = Field(default=3600, ge=60, le=86_400)
    maintenance_task_soft_time_limit_seconds: int = Field(
        default=3300, ge=30, le=86_399
    )
    notification_email_enabled: bool = False
    notification_email_sender_user_id: str | None = None
    notification_email_reply_to: EmailStr | None = None
    notification_email_max_recipients: int = Field(default=100, ge=1, le=500)
    notification_teams_enabled: bool = False
    notification_teams_mode: Literal[
        "INCOMING_WEBHOOK", "WORKFLOW_WEBHOOK", "GRAPH"
    ] = "WORKFLOW_WEBHOOK"
    notification_teams_webhook_url: SecretStr | None = None
    notification_telegram_enabled: bool = False
    telegram_bot_token: SecretStr | None = None
    telegram_default_chat_id: str | None = None
    secret_provider: Literal["environment", "azure_key_vault"] = "environment"
    azure_key_vault_url: str | None = None
    encryption_key: SecretStr | None = None
    encryption_key_version: str = Field(default="v1", min_length=1, max_length=50)
    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = Field(default=10, ge=1, le=10_000)
    rate_limit_upload_per_minute: int = Field(default=20, ge=1, le=10_000)
    rate_limit_reports_per_hour: int = Field(default=20, ge=1, le=100_000)
    rate_limit_sync_per_hour: int = Field(default=10, ge=1, le=100_000)
    rate_limit_connection_test_per_minute: int = Field(default=5, ge=1, le=10_000)
    log_format: Literal["console", "json"] = "console"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    metrics_enabled: bool = True
    metrics_auth_token: SecretStr | None = None
    otel_enabled: bool = False
    otel_service_name: str = "document-compliance-api"
    otel_exporter_otlp_endpoint: str | None = None
    otel_trace_sample_ratio: float = Field(default=0.10, ge=0.0, le=1.0)
    malware_scanning_enabled: bool = False
    malware_scanner: Literal["noop", "clamav"] = "clamav"
    clamav_host: str = "clamav"
    clamav_port: int = Field(default=3310, ge=1, le=65_535)
    malware_scan_timeout_seconds: int = Field(default=120, ge=1, le=3600)
    malware_scanner_failure_policy: Literal["FAIL_CLOSED", "FAIL_OPEN_WITH_WARNING"] = (
        "FAIL_CLOSED"
    )
    celery_task_acks_late: bool = True
    celery_task_reject_on_worker_lost: bool = True
    celery_worker_prefetch_multiplier: int = Field(default=1, ge=1, le=100)
    celery_result_expires_seconds: int = Field(default=86_400, ge=60)
    celery_broker_connection_retry_on_startup: bool = True
    auto_run_ocr_after_extraction: bool = False
    auto_run_language_detection_after_extraction: bool = False
    auto_run_language_detection_after_ocr: bool = False

    @field_validator("default_company_code")
    @classmethod
    def validate_default_company_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if (
            not normalized
            or not normalized.isascii()
            or not all(
                character.isalnum() or character == "_" for character in normalized
            )
        ):
            raise ValueError(
                "DEFAULT_COMPANY_CODE may contain only letters, numbers, "
                "and underscore."
            )
        return normalized

    @field_validator("application_timezone")
    @classmethod
    def validate_application_timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError(
                "APP_TIMEZONE must be a valid IANA timezone name."
            ) from exc
        return normalized

    @field_validator(
        "public_app_url",
        "api_base_url",
        "microsoft_graph_base_url",
    )
    @classmethod
    def validate_service_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Service URLs must use http:// or https://.")
        return normalized

    @field_validator(
        "sharepoint_site_hostname",
        "sharepoint_site_path",
        "sharepoint_site_id",
        "sharepoint_drive_id",
        "sharepoint_library_name",
        "sharepoint_webhook_notification_url",
        "notification_email_sender_user_id",
        "telegram_default_chat_id",
        "azure_key_vault_url",
        "otel_exporter_otlp_endpoint",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator(
        "microsoft_client_certificate_path",
        "notification_email_reply_to",
        mode="before",
    )
    @classmethod
    def normalize_optional_typed_value(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("sharepoint_root_folder_path")
    @classmethod
    def validate_sharepoint_root_folder_path(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/").strip("/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or "\x00" in normalized
        ):
            raise ValueError(
                "SHAREPOINT_ROOT_FOLDER_PATH must be a safe relative path."
            )
        return path.as_posix()

    @field_validator("redis_key_prefix")
    @classmethod
    def validate_redis_key_prefix(cls, value: str) -> str:
        normalized = value.strip().strip(":")
        if (
            not normalized
            or len(normalized) > 200
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("REDIS_KEY_PREFIX must be a bounded key namespace.")
        return normalized

    @field_validator(
        "storage_documents_prefix",
        "storage_temp_prefix",
        "storage_quarantine_prefix",
        "storage_deleted_prefix",
    )
    @classmethod
    def validate_storage_prefix(cls, value: str) -> str:
        """Require normalized relative keys below the configured root."""
        normalized = value.strip().replace("\\", "/").strip("/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or ":" in normalized
            or "\x00" in normalized
        ):
            raise ValueError("Storage prefixes must be safe relative POSIX paths.")
        return path.as_posix()

    @field_validator("allowed_document_extensions")
    @classmethod
    def validate_allowed_document_extensions(cls, value: str) -> str:
        """Only allow a non-empty subset of the Phase 5 format whitelist."""
        supported = {".pdf", ".docx", ".xlsx"}
        normalized = {
            extension.strip().lower()
            for extension in value.split(",")
            if extension.strip()
        }
        normalized = {
            extension if extension.startswith(".") else f".{extension}"
            for extension in normalized
        }
        if not normalized or not normalized.issubset(supported):
            raise ValueError(
                "ALLOWED_DOCUMENT_EXTENSIONS may contain only .pdf, .docx, and .xlsx."
            )
        return ",".join(sorted(normalized))

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.strip()
        normalized = normalized.rstrip("/")
        if normalized != "/api/v1":
            raise ValueError("The Phase 1 API prefix is fixed at '/api/v1'.")
        return normalized

    @field_validator(
        "celery_broker_url",
        "celery_result_backend",
    )
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("redis://", "rediss://")):
            raise ValueError("Celery Redis URLs must use redis:// or rediss://.")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw_value = value.get_secret_value()
        if not raw_value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg SQLAlchemy driver."
            )
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().strip()) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters.")
        return value

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Self:
        if self.environment == "production" and self.backend_debug:
            raise ValueError("BACKEND_DEBUG must be false in production.")
        if self.database_url is None and (
            self.postgres_password is None
            or not self.postgres_password.get_secret_value()
        ):
            raise ValueError(
                "POSTGRES_PASSWORD is required when DATABASE_URL is not set."
            )
        if (
            self.extraction_task_soft_time_limit_seconds
            >= self.extraction_task_time_limit_seconds
        ):
            raise ValueError(
                "EXTRACTION_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "EXTRACTION_TASK_TIME_LIMIT_SECONDS."
            )
        if self.ocr_task_soft_time_limit_seconds >= self.ocr_task_time_limit_seconds:
            raise ValueError(
                "OCR_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "OCR_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.language_task_soft_time_limit_seconds
            >= self.language_task_time_limit_seconds
        ):
            raise ValueError(
                "LANGUAGE_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "LANGUAGE_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.compliance_task_soft_time_limit_seconds
            >= self.compliance_task_time_limit_seconds
        ):
            raise ValueError(
                "COMPLIANCE_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "COMPLIANCE_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.similarity_task_soft_time_limit_seconds
            >= self.similarity_task_time_limit_seconds
        ):
            raise ValueError(
                "SIMILARITY_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "SIMILARITY_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.glossary_task_soft_time_limit_seconds
            >= self.glossary_task_time_limit_seconds
        ):
            raise ValueError(
                "GLOSSARY_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "GLOSSARY_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.revision_comparison_task_soft_time_limit_seconds
            >= self.revision_comparison_task_time_limit_seconds
        ):
            raise ValueError(
                "REVISION_COMPARISON_TASK_SOFT_TIME_LIMIT_SECONDS must be "
                "lower than REVISION_COMPARISON_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.reporting_task_soft_time_limit_seconds
            >= self.reporting_task_time_limit_seconds
        ):
            raise ValueError(
                "REPORTING_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "REPORT_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.sharepoint_task_soft_time_limit_seconds
            >= self.sharepoint_task_time_limit_seconds
        ):
            raise ValueError(
                "SHAREPOINT_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "SHAREPOINT_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.notification_task_soft_time_limit_seconds
            >= self.notification_task_time_limit_seconds
        ):
            raise ValueError(
                "NOTIFICATION_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "NOTIFICATION_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.maintenance_task_soft_time_limit_seconds
            >= self.maintenance_task_time_limit_seconds
        ):
            raise ValueError(
                "MAINTENANCE_TASK_SOFT_TIME_LIMIT_SECONDS must be lower than "
                "MAINTENANCE_TASK_TIME_LIMIT_SECONDS."
            )
        if (
            self.microsoft_graph_retry_base_seconds
            > self.microsoft_graph_retry_max_seconds
        ):
            raise ValueError(
                "MICROSOFT_GRAPH_RETRY_BASE_SECONDS must not exceed "
                "MICROSOFT_GRAPH_RETRY_MAX_SECONDS."
            )
        upload_chunk_bytes = self.sharepoint_upload_chunk_size_mb * 1024 * 1024
        if upload_chunk_bytes % (320 * 1024) != 0:
            raise ValueError(
                "SHAREPOINT_UPLOAD_CHUNK_SIZE_MB must produce a chunk size "
                "divisible by 320 KiB."
            )
        if (
            self.sharepoint_simple_upload_max_mb
            > self.sharepoint_upload_max_file_size_mb
        ):
            raise ValueError(
                "SHAREPOINT_SIMPLE_UPLOAD_MAX_MB must not exceed "
                "SHAREPOINT_UPLOAD_MAX_FILE_SIZE_MB."
            )
        if self.sharepoint_sync_enabled and not self.microsoft_graph_enabled:
            raise ValueError(
                "MICROSOFT_GRAPH_ENABLED is required when SharePoint sync is enabled."
            )
        if (
            self.storage_provider in {"sharepoint", "hybrid"}
            and not self.microsoft_graph_enabled
        ):
            raise ValueError(
                "MICROSOFT_GRAPH_ENABLED is required for SharePoint storage."
            )
        if (
            self.storage_provider in {"sharepoint", "hybrid"}
            and not self.sharepoint_drive_id
        ):
            raise ValueError("SHAREPOINT_DRIVE_ID is required for SharePoint storage.")
        if self.microsoft_graph_enabled:
            if not self.microsoft_tenant_id or not self.microsoft_client_id:
                raise ValueError(
                    "Microsoft tenant and client IDs are required when Graph "
                    "is enabled."
                )
            if self.microsoft_graph_auth_mode == "client_secret" and (
                self.microsoft_client_secret is None
                or not self.microsoft_client_secret.get_secret_value()
            ):
                raise ValueError(
                    "MICROSOFT_CLIENT_SECRET is required for client-secret auth."
                )
            if (
                self.microsoft_graph_auth_mode == "certificate"
                and self.microsoft_client_certificate_path is None
            ):
                raise ValueError(
                    "MICROSOFT_CLIENT_CERTIFICATE_PATH is required for "
                    "certificate auth."
                )
        if self.sharepoint_webhook_enabled:
            if (
                not self.sharepoint_webhook_notification_url
                or not self.sharepoint_webhook_notification_url.startswith("https://")
            ):
                raise ValueError(
                    "An HTTPS SharePoint webhook notification URL is required."
                )
            if (
                self.sharepoint_webhook_client_state is None
                or not self.sharepoint_webhook_client_state.get_secret_value()
            ):
                raise ValueError(
                    "SHAREPOINT_WEBHOOK_CLIENT_STATE is required for webhooks."
                )
        if self.notification_email_enabled and (
            not self.microsoft_graph_enabled
            or not self.notification_email_sender_user_id
        ):
            raise ValueError(
                "Graph and a fixed sender are required for email notifications."
            )
        if self.notification_teams_enabled and (
            self.notification_teams_mode != "GRAPH"
            and (
                self.notification_teams_webhook_url is None
                or not self.notification_teams_webhook_url.get_secret_value()
            )
        ):
            raise ValueError(
                "NOTIFICATION_TEAMS_WEBHOOK_URL is required for webhook modes."
            )
        if self.notification_telegram_enabled and (
            self.telegram_bot_token is None
            or not self.telegram_bot_token.get_secret_value()
            or not self.telegram_default_chat_id
        ):
            raise ValueError(
                "Telegram token and default chat ID are required when enabled."
            )
        if not (
            self.similarity_critical_low_threshold
            <= self.similarity_review_threshold
            <= self.similarity_acceptable_threshold
            <= self.similarity_high_threshold
        ):
            raise ValueError(
                "Similarity thresholds must be ordered from critical-low through high."
            )
        if (
            self.similarity_chunk_overlap_characters
            >= self.similarity_chunk_max_characters
        ):
            raise ValueError(
                "SIMILARITY_CHUNK_OVERLAP_CHARACTERS must be lower than "
                "SIMILARITY_CHUNK_MAX_CHARACTERS."
            )
        if self.report_include_full_text:
            raise ValueError("REPORT_INCLUDE_FULL_TEXT must remain false.")
        if self.ocr_low_confidence_threshold > self.ocr_review_confidence_threshold:
            raise ValueError(
                "OCR_LOW_CONFIDENCE_THRESHOLD must not exceed "
                "OCR_REVIEW_CONFIDENCE_THRESHOLD."
            )
        if self.language_confidence_minimum > self.language_confidence_review_threshold:
            raise ValueError(
                "LANGUAGE_CONFIDENCE_MINIMUM must not exceed "
                "LANGUAGE_CONFIDENCE_REVIEW_THRESHOLD."
            )
        if self.section_match_min_confidence > self.section_fuzzy_match_threshold:
            raise ValueError(
                "SECTION_MATCH_MIN_CONFIDENCE must not exceed "
                "SECTION_FUZZY_MATCH_THRESHOLD."
            )
        if self.environment == "production":
            if not self.public_app_url.startswith("https://"):
                raise ValueError("PUBLIC_APP_URL must use HTTPS in production.")
            if not self.api_base_url.startswith("https://"):
                raise ValueError("API_BASE_URL must use HTTPS in production.")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS origins are forbidden in production.")
            if not self.trusted_host_list or "*" in self.trusted_host_list:
                raise ValueError("Explicit TRUSTED_HOSTS are required in production.")
            if (
                self.encryption_key is None
                or not self.encryption_key.get_secret_value()
            ):
                raise ValueError("ENCRYPTION_KEY is required in production.")
            try:
                encryption_key = base64.b64decode(
                    self.encryption_key.get_secret_value(),
                    validate=True,
                )
            except (binascii.Error, ValueError) as exc:
                raise ValueError(
                    "ENCRYPTION_KEY must be valid base64 in production."
                ) from exc
            if len(encryption_key) not in {16, 24, 32}:
                raise ValueError(
                    "ENCRYPTION_KEY must decode to a valid AES key length."
                )
            if (
                self.redis_password is None
                or not self.redis_password.get_secret_value()
            ):
                raise ValueError("REDIS_PASSWORD is required in production.")
            if (
                urlparse(self.celery_broker_url).password is None
                or urlparse(self.celery_result_backend).password is None
            ):
                raise ValueError(
                    "Production Celery Redis URLs must include authentication."
                )
            if self.redis_key_prefix.casefold().endswith(":development"):
                raise ValueError(
                    "Production Redis keys require a non-development namespace."
                )
            if self.log_format != "json":
                raise ValueError("LOG_FORMAT=json is required in production.")
            if (
                self.malware_scanning_enabled
                and self.malware_scanner_failure_policy != "FAIL_CLOSED"
            ):
                raise ValueError("Production malware scanning must use FAIL_CLOSED.")
        _ = self.cors_origin_list
        return self

    @property
    def debug(self) -> bool:
        """Expose the namespaced debug setting to the application factory."""
        return self.backend_debug

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the database URL only at the infrastructure boundary."""
        if self.database_url is not None:
            return self.database_url.get_secret_value()

        assert self.postgres_password is not None
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse JSON-array or comma-separated CORS configuration."""
        raw_value = self.cors_origins.strip()
        if not raw_value:
            return []

        if raw_value.startswith("["):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "BACKEND_CORS_ORIGINS must contain valid JSON."
                ) from exc
            if not isinstance(parsed, list) or not all(
                isinstance(origin, str) for origin in parsed
            ):
                raise ValueError(
                    "BACKEND_CORS_ORIGINS JSON value must be a list of strings."
                )
            origins = parsed
        else:
            origins = raw_value.split(",")

        normalized = [
            origin.strip().rstrip("/") for origin in origins if origin.strip()
        ]
        if not normalized:
            return []
        for origin in normalized:
            if origin != "*" and not origin.startswith(("http://", "https://")):
                raise ValueError(
                    "Each CORS origin must be '*', an http URL, or an https URL."
                )
        return normalized

    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def trusted_proxy_ip_list(self) -> list[str]:
        return [
            network.strip()
            for network in self.trusted_proxy_ips.split(",")
            if network.strip()
        ]

    @property
    def allowed_document_extension_set(self) -> frozenset[str]:
        """Return the configured extension whitelist with leading dots."""
        return frozenset(self.allowed_document_extensions.split(","))

    @property
    def document_max_file_size_bytes(self) -> int:
        return self.document_max_file_size_mb * 1024 * 1024

    @property
    def document_batch_max_total_size_bytes(self) -> int:
        return self.document_batch_max_total_size_mb * 1024 * 1024

    @property
    def document_single_upload_request_limit_bytes(self) -> int:
        """Allow bounded multipart framing beyond one configured file."""
        return self.document_max_file_size_bytes + (2 * 1024 * 1024)

    @property
    def document_batch_upload_request_limit_bytes(self) -> int:
        """Allow bounded multipart framing for the configured batch count."""
        overhead = max(
            2 * 1024 * 1024,
            self.document_batch_max_files * 64 * 1024,
        )
        return self.document_batch_max_total_size_bytes + overhead

    @property
    def request_body_max_size_bytes(self) -> int:
        """Global ceiling for routes without a stricter upload limit."""
        return max(
            self.document_single_upload_request_limit_bytes,
            self.document_batch_upload_request_limit_bytes,
        )

    @property
    def file_download_chunk_size_bytes(self) -> int:
        return self.file_download_chunk_size_kb * 1024

    @property
    def ooxml_max_uncompressed_size_bytes(self) -> int:
        return self.ooxml_max_uncompressed_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""
    return Settings()
