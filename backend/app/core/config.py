"""Environment-backed application configuration."""

import json
from functools import lru_cache
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
    app_version: str = "0.4.0"
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

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        normalized = value.strip()
        normalized = normalized.rstrip("/")
        if normalized != "/api/v1":
            raise ValueError("The Phase 1 API prefix is fixed at '/api/v1'.")
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


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""
    return Settings()
