"""Health-check application service."""

import asyncio
import importlib.util
from pathlib import Path
from typing import Literal

from celery.exceptions import CeleryError
from kombu.exceptions import KombuError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.schemas.health import DependencyHealthData, HealthData
from app.workers.celery_app import celery_app

DependencyState = Literal["healthy", "unavailable"]


class HealthService:
    """Build the API liveness representation."""

    def get_health(self, *, version: str) -> HealthData:
        return HealthData(version=version)

    async def get_dependency_health(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
    ) -> DependencyHealthData:
        """Probe infrastructure without importing or initializing large models."""
        database = await self._database_state(session)
        redis = await self._redis_state(settings)
        workers = await asyncio.to_thread(self._worker_states)
        return DependencyHealthData(
            database=database,
            redis=redis,
            extraction_worker=workers["extraction"],
            ocr_worker=workers["ocr"],
            language_worker=workers["language"],
            compliance_worker=workers["compliance"],
            ocr_provider=self._ocr_provider_state(settings),
            language_model=self._file_state(settings.language_model_path),
            similarity_model=self._similarity_model_state(settings),
            glossary_service=database,
            revision_comparison_worker=workers["revision"],
            reporting_worker=workers["reporting"],
        )

    @staticmethod
    async def _database_state(session: AsyncSession) -> DependencyState:
        try:
            await session.execute(text("SELECT 1"))
        except (OSError, SQLAlchemyError):
            return "unavailable"
        return "healthy"

    @staticmethod
    async def _redis_state(settings: Settings) -> DependencyState:
        client = Redis.from_url(
            settings.celery_broker_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            return "healthy" if await client.ping() else "unavailable"
        except (OSError, RedisError):
            return "unavailable"
        finally:
            await client.aclose()

    @staticmethod
    def _worker_states() -> dict[str, DependencyState]:
        states: dict[str, DependencyState] = {
            "extraction": "unavailable",
            "ocr": "unavailable",
            "language": "unavailable",
            "compliance": "unavailable",
            "similarity": "unavailable",
            "glossary": "unavailable",
            "revision": "unavailable",
            "reporting": "unavailable",
        }
        try:
            replies = celery_app.control.inspect(timeout=1).ping() or {}
        except (CeleryError, KombuError, OSError, TimeoutError):
            return states
        for node in replies:
            prefix = node.split("@", maxsplit=1)[0]
            if prefix in states:
                states[prefix] = "healthy"
        return states

    @classmethod
    def _ocr_provider_state(cls, settings: Settings) -> DependencyState:
        if importlib.util.find_spec("paddleocr") is None:
            return "unavailable"
        required_directories = (
            settings.ocr_model_root / "latin" / "detection",
            settings.ocr_model_root / "latin" / "recognition",
            settings.ocr_model_root / "chinese_simplified" / "detection",
            settings.ocr_model_root / "chinese_simplified" / "recognition",
        )
        return (
            "healthy"
            if all(cls._directory_has_model(path) for path in required_directories)
            else "unavailable"
        )

    @staticmethod
    def _directory_has_model(path: Path) -> bool:
        return path.is_dir() and any(
            child.is_file() and child.name != ".gitkeep" for child in path.rglob("*")
        )

    @staticmethod
    def _file_state(path: Path) -> DependencyState:
        return (
            "healthy" if path.is_file() and path.stat().st_size > 0 else "unavailable"
        )

    @staticmethod
    def _similarity_model_state(settings: Settings) -> DependencyState:
        root = settings.similarity_model_path
        safe_name = settings.similarity_model_name.replace("/", "--")
        candidates = (root, root / safe_name)
        return (
            "healthy"
            if any(
                candidate.is_dir()
                and (
                    (candidate / "config.json").is_file()
                    or (candidate / "modules.json").is_file()
                )
                for candidate in candidates
            )
            else "unavailable"
        )


def get_health_service() -> HealthService:
    """FastAPI dependency provider for the health service."""
    return HealthService()
