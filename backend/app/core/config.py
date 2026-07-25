"""Environment-backed application configuration."""

import json
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Literal, Self
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

    app_name: str = "Document Compliance API"
    app_version: str = "0.7.0"
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV"),
    )
    backend_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: SecretStr | None = None
    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "document_compliance"
    postgres_user: str = "document_compliance"
    postgres_password: SecretStr | None = None
    database_echo: bool = False
    cors_origins: str = Field(
        default='["http://localhost:5173"]',
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS"),
    )
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
    storage_provider: Literal["local"] = "local"
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
        "https://dl.fbaipublicfiles.com/fasttext/"
        "supervised-models/lid.176.bin"
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
    auto_run_ocr_after_extraction: bool = False
    auto_run_language_detection_after_extraction: bool = False
    auto_run_language_detection_after_ocr: bool = False

    @field_validator("default_company_code")
    @classmethod
    def validate_default_company_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or not normalized.isascii() or not all(
            character.isalnum() or character == "_"
            for character in normalized
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
            raise ValueError(
                "Storage prefixes must be safe relative POSIX paths."
            )
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
                "ALLOWED_DOCUMENT_EXTENSIONS may contain only "
                ".pdf, .docx, and .xlsx."
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
            raise ValueError(
                "Celery Redis URLs must use redis:// or rediss://."
            )
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
        if (
            self.ocr_task_soft_time_limit_seconds
            >= self.ocr_task_time_limit_seconds
        ):
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
            self.ocr_low_confidence_threshold
            > self.ocr_review_confidence_threshold
        ):
            raise ValueError(
                "OCR_LOW_CONFIDENCE_THRESHOLD must not exceed "
                "OCR_REVIEW_CONFIDENCE_THRESHOLD."
            )
        if (
            self.language_confidence_minimum
            > self.language_confidence_review_threshold
        ):
            raise ValueError(
                "LANGUAGE_CONFIDENCE_MINIMUM must not exceed "
                "LANGUAGE_CONFIDENCE_REVIEW_THRESHOLD."
            )
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

        normalized = [origin.strip().rstrip("/") for origin in origins if origin.strip()]
        if not normalized:
            return []
        for origin in normalized:
            if origin != "*" and not origin.startswith(("http://", "https://")):
                raise ValueError(
                    "Each CORS origin must be '*', an http URL, or an https URL."
                )
        return normalized

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
