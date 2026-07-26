"""Test environment bootstrap."""

import os

os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://test_user:test_password@localhost:5432/test_compliance"
)
os.environ["APP_ENV"] = "test"
os.environ["APP_VERSION"] = "0.8.0"
os.environ["MASTER_DATA_IMPORT_MAX_ROWS"] = "5000"
os.environ["MASTER_DATA_EXPORT_MAX_ROWS"] = "50000"
os.environ["DEFAULT_COMPANY_CODE"] = "MTI"
os.environ["DOCUMENT_REGISTER_IMPORT_MAX_ROWS"] = "10000"
os.environ["DOCUMENT_REGISTER_EXPORT_MAX_ROWS"] = "100000"
os.environ["DOCUMENT_IMPORT_MAX_FILE_SIZE_MB"] = "25"
os.environ["DOCUMENT_NUMBER_MAX_LENGTH"] = "50"
os.environ["DOCUMENT_TITLE_MAX_LENGTH"] = "500"
os.environ["ARCHIVE_REASON_MAX_LENGTH"] = "1000"
os.environ["APP_TIMEZONE"] = "Asia/Makassar"
os.environ["BACKEND_DEBUG"] = "false"
os.environ["BACKEND_CORS_ORIGINS"] = '["http://localhost:5173"]'
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-key-with-at-least-32-characters"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["JWT_REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["MAX_LOGIN_ATTEMPTS"] = "3"
os.environ["ACCOUNT_LOCK_MINUTES"] = "15"
os.environ["DEFAULT_ADMIN_NAME"] = "Test Administrator"
os.environ["DEFAULT_ADMIN_EMAIL"] = "admin@example.com"
os.environ["DEFAULT_ADMIN_PASSWORD"] = "Admin123"

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
import pytest_asyncio
from argon2 import PasswordHasher
from argon2.low_level import Type
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.models
from app.api.dependencies.auth import get_password_service, get_token_service
from app.core.authorization import UserRole
from app.core.config import get_settings
from app.database.base import Base
from app.database.session import get_db_session
from app.main import app
from app.models.user import User
from app.services.auth.password_service import PasswordService
from app.services.auth.token_service import TokenService

TestSessionFactory = async_sessionmaker[AsyncSession]
UserFactory = Callable[..., Any]


@pytest.fixture
def password_service() -> PasswordService:
    """Use valid but inexpensive Argon2id parameters in the test suite."""
    hasher = PasswordHasher(
        time_cost=1,
        memory_cost=1024,
        parallelism=1,
        hash_len=16,
        salt_len=16,
        type=Type.ID,
    )
    return PasswordService(hasher)


@pytest.fixture
def token_service() -> TokenService:
    return TokenService(get_settings())


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[TestSessionFactory]:
    """Create one isolated in-memory async database for each test."""
    test_engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def create_user(
    session_factory: TestSessionFactory,
    password_service: PasswordService,
) -> UserFactory:
    async def factory(**overrides: Any) -> User:
        values: dict[str, Any] = {
            "name": "Test User",
            "email": "user@example.com",
            "password_hash": password_service.hash_password("Valid123"),
            "role": UserRole.VIEWER,
            "department_id": None,
            "is_active": True,
            "is_superuser": False,
            "failed_login_attempts": 0,
            "locked_until": None,
        }
        values.update(overrides)
        user = User(**values)
        async with session_factory() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    return factory


@pytest_asyncio.fixture
async def api_client(
    session_factory: TestSessionFactory,
    password_service: PasswordService,
    token_service: TokenService,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_password_service] = lambda: password_service
    app.dependency_overrides[get_token_service] = lambda: token_service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()
