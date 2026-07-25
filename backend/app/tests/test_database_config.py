"""Database configuration and async-engine tests."""

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.database.session import AsyncSessionFactory, engine


def test_database_engine_uses_async_postgresql_driver() -> None:
    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.dialect.is_async is True
    assert AsyncSessionFactory.kw["expire_on_commit"] is False


def test_settings_accept_json_and_csv_cors_origins() -> None:
    common = {
        "database_url": "postgresql+asyncpg://user:password@localhost:5432/app"
    }
    json_settings = Settings(
        **common,
        cors_origins='["http://localhost:5173", "https://example.com/"]',
    )
    csv_settings = Settings(
        **common,
        cors_origins="http://localhost:5173,https://example.com/",
    )

    expected = ["http://localhost:5173", "https://example.com"]
    assert json_settings.cors_origin_list == expected
    assert csv_settings.cors_origin_list == expected


def test_settings_use_namespaced_cors_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://ambient.invalid")
    monkeypatch.setenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,https://frontend.example.com/",
    )

    settings = Settings(
        database_url="postgresql+asyncpg://user:password@localhost:5432/app"
    )

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "https://frontend.example.com",
    ]


def test_phase_four_version_and_document_register_defaults() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:password@localhost:5432/app",
    )

    assert settings.app_version == "0.5.0"
    assert settings.default_company_code == "MTI"
    assert settings.document_register_import_max_rows == 10_000
    assert settings.document_register_export_max_rows == 100_000
    assert settings.document_import_max_file_size_mb == 25


def test_settings_reject_synchronous_database_driver() -> None:
    with pytest.raises(ValidationError, match=r"postgresql\+asyncpg"):
        Settings(database_url="postgresql://user:password@localhost:5432/app")


def test_settings_uses_namespaced_debug_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.setenv("BACKEND_DEBUG", "true")

    settings = Settings(
        database_url="postgresql+asyncpg://user:password@localhost:5432/app"
    )

    assert settings.debug is True


def test_settings_ignore_unrelated_ambient_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKEND_DEBUG", raising=False)
    monkeypatch.setenv("DEBUG", "release")

    settings = Settings(
        database_url="postgresql+asyncpg://user:password@localhost:5432/app"
    )

    assert settings.debug is False


def test_settings_reject_debug_in_production() -> None:
    with pytest.raises(ValidationError, match="BACKEND_DEBUG"):
        Settings(
            database_url="postgresql+asyncpg://user:password@localhost:5432/app",
            environment="production",
            backend_debug=True,
        )


def test_component_database_url_safely_encodes_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    settings = Settings(
        database_host="postgres",
        postgres_db="compliance",
        postgres_user="document_user",
        postgres_password="p@ss:/?#word",
    )

    parsed_url = make_url(settings.sqlalchemy_database_url)

    assert parsed_url.drivername == "postgresql+asyncpg"
    assert parsed_url.host == "postgres"
    assert parsed_url.password == "p@ss:/?#word"


def test_api_prefix_is_fixed_for_phase_one() -> None:
    with pytest.raises(ValidationError, match="fixed at '/api/v1'"):
        Settings(
            database_url="postgresql+asyncpg://user:password@localhost:5432/app",
            api_v1_prefix="/api/v2",
        )
