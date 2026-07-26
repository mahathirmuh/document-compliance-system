"""Sanitized dead-letter persistence, retry, and dismissal."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from http import HTTPStatus
from math import ceil
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.log_redaction import redact_sensitive
from app.models.dead_letter_job import DeadLetterJob, DeadLetterStatus
from app.repositories.dead_letter_job_repository import (
    DeadLetterJobRepository,
)
from app.schemas.dead_letter import (
    DeadLetterJobResponse,
    DeadLetterListResponse,
    DeadLetterMutationResponse,
)
from app.services.notification.errors import notification_error
from app.utils.datetime import utc_now


class DeadLetterRetryPublisher(Protocol):
    async def publish(
        self,
        *,
        task_name: str,
        arguments: Mapping[str, Any],
        dead_letter_job_id: UUID,
    ) -> str | None: ...


def _json_safe(value: Any) -> Any:
    redacted = redact_sensitive(value)
    if isinstance(redacted, Mapping):
        return {str(key): _json_safe(item) for key, item in redacted.items()}
    if isinstance(redacted, (list, tuple, set)):
        return [_json_safe(item) for item in redacted]
    if isinstance(redacted, (str, int, float, bool)) or redacted is None:
        return redacted
    return str(redacted)


class DeadLetterService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        publisher: DeadLetterRetryPublisher | None = None,
    ) -> None:
        self.session = session
        self.repository = DeadLetterJobRepository(session)
        self.publisher = publisher

    async def list(
        self,
        *,
        status: DeadLetterStatus | None,
        task_name: str | None,
        page: int,
        page_size: int,
    ) -> DeadLetterListResponse:
        rows, total = await self.repository.list_page(
            status=status,
            task_name=task_name,
            page=page,
            page_size=page_size,
        )
        return DeadLetterListResponse(
            items=[DeadLetterJobResponse.model_validate(row) for row in rows],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def record(
        self,
        *,
        task_name: str,
        entity_type: str,
        entity_id: UUID | None,
        attempts: int,
        maximum_attempts: int,
        arguments: Mapping[str, Any],
        error_code: str,
        safe_error: str,
        failed_at: datetime | None = None,
    ) -> DeadLetterJob:
        timestamp = failed_at or utc_now()
        sanitized_arguments = _json_safe(arguments)
        existing = await self.repository.get_open_for_entity(
            task_name=task_name[:500],
            entity_type=entity_type[:100],
            entity_id=entity_id,
            for_update=True,
        )
        if existing is not None:
            existing.status = DeadLetterStatus.ACTIVE
            existing.attempts = attempts
            existing.maximum_attempts = maximum_attempts
            existing.sanitized_arguments_json = sanitized_arguments
            existing.error_code = error_code[:100]
            existing.last_error = safe_error[:2000]
            existing.last_failed_at = timestamp
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        job = DeadLetterJob(
            task_name=task_name[:500],
            entity_type=entity_type[:100],
            entity_id=entity_id,
            status=DeadLetterStatus.ACTIVE,
            attempts=attempts,
            maximum_attempts=maximum_attempts,
            sanitized_arguments_json=sanitized_arguments,
            error_code=error_code[:100],
            last_error=safe_error[:2000],
            first_failed_at=timestamp,
            last_failed_at=timestamp,
            retry_history_json=[],
        )
        await self.repository.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def mark_retried_for_entity(
        self,
        *,
        task_name: str,
        entity_type: str,
        entity_id: UUID,
    ) -> None:
        job = await self.repository.get_open_for_entity(
            task_name=task_name,
            entity_type=entity_type,
            entity_id=entity_id,
            for_update=True,
        )
        if job is None:
            return
        job.status = DeadLetterStatus.RETRIED
        history = list(job.retry_history_json)
        history.append({"completedAt": utc_now().isoformat()})
        job.retry_history_json = history[-100:]
        await self.session.commit()

    async def retry(self, job_id: UUID) -> DeadLetterMutationResponse:
        job = await self._get(job_id, for_update=True)
        if job.status not in {
            DeadLetterStatus.ACTIVE,
            DeadLetterStatus.RETRIED,
        }:
            raise notification_error(
                "Dead-letter job cannot be retried in its current state.",
                code="DEAD_LETTER_JOB_NOT_RETRYABLE",
                status_code=HTTPStatus.CONFLICT,
            )
        if self.publisher is None:
            raise notification_error(
                "Dead-letter retry publisher is not configured.",
                code="DEAD_LETTER_RETRY_UNAVAILABLE",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        provider_id = await self.publisher.publish(
            task_name=job.task_name,
            arguments=job.sanitized_arguments_json,
            dead_letter_job_id=job.id,
        )
        history = list(job.retry_history_json)
        history.append(
            {
                "queuedAt": utc_now().isoformat(),
                "providerTaskId": provider_id,
            }
        )
        job.retry_history_json = history[-100:]
        job.status = DeadLetterStatus.RETRY_QUEUED
        await self.session.commit()
        return DeadLetterMutationResponse(job_id=job.id, status=job.status)

    async def dismiss(
        self,
        job_id: UUID,
        *,
        actor_id: UUID,
        reason: str,
    ) -> DeadLetterMutationResponse:
        job = await self._get(job_id, for_update=True)
        if job.status == DeadLetterStatus.DISMISSED:
            raise notification_error(
                "Dead-letter job is already dismissed.",
                code="DEAD_LETTER_JOB_ALREADY_DISMISSED",
                status_code=HTTPStatus.CONFLICT,
            )
        job.status = DeadLetterStatus.DISMISSED
        job.dismissed_at = utc_now()
        job.dismissed_by = actor_id
        job.dismissal_reason = reason[:2000]
        await self.session.commit()
        return DeadLetterMutationResponse(job_id=job.id, status=job.status)

    async def _get(
        self,
        job_id: UUID,
        *,
        for_update: bool,
    ) -> DeadLetterJob:
        job = await self.repository.get_by_id(job_id, for_update=for_update)
        if job is None:
            raise notification_error(
                "Dead-letter job was not found.",
                code="DEAD_LETTER_JOB_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return job
