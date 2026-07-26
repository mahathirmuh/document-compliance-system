"""Async PostgreSQL engine and request-scoped session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.sqlalchemy_database_url,
    connect_args={
        "timeout": settings.db_connect_timeout_seconds,
        "server_settings": {
            "application_name": "document-compliance-api",
            "statement_timeout": str(settings.db_statement_timeout_ms),
        },
    },
    echo=settings.database_echo,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_size=settings.db_pool_size,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_pre_ping=True,
)
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield one transaction-aware SQLAlchemy session per request."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Close engine connection pools during application shutdown."""
    await engine.dispose()
