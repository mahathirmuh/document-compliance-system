"""Dry-run-first, batched, legal-hold-aware retention execution."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.data_retention_policy import RetentionEntityType
from app.repositories.audit_log import AuditLogRepository
from app.repositories.data_retention_policy_repository import (
    DataRetentionPolicyRepository,
)
from app.schemas.retention import RetentionRunResponse
from app.services.notification.errors import notification_error
from app.services.retention.contracts import RetentionEntityHandler
from app.utils.datetime import utc_now


class RetentionAuditSink(Protocol):
    async def record_summary(self, summary: RetentionRunResponse) -> None: ...


class RetentionService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        handlers: Mapping[RetentionEntityType, RetentionEntityHandler],
        audit_sink: RetentionAuditSink | None = None,
        allow_sole_copy_deletion: bool = False,
        actor_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.repository = DataRetentionPolicyRepository(session)
        self.handlers = dict(handlers)
        self.audit_sink = audit_sink
        self.allow_sole_copy_deletion = allow_sole_copy_deletion
        self.actor_id = actor_id
        self.audit = AuditLogRepository(session)

    async def run(
        self,
        *,
        entity_type: RetentionEntityType,
        dry_run: bool,
        batch_size: int,
    ) -> RetentionRunResponse:
        handler = self.handlers.get(entity_type)
        if handler is None:
            raise notification_error(
                "No retention handler is configured for this entity type.",
                code="RETENTION_JOB_FAILED",
            )
        policies = await self.repository.active_for_entity(entity_type)
        if not policies:
            raise notification_error(
                "No active retention policy exists for this entity type.",
                code="RETENTION_POLICY_NOT_FOUND",
            )
        now = utc_now()
        scanned = eligible = archived = soft_deleted = permanently_deleted = 0
        legal_hold_skipped = 0
        warnings: list[str] = []
        remaining = max(1, min(batch_size, 5000))
        for policy in policies:
            if remaining <= 0:
                break
            delete_days = policy.delete_after_days or policy.retention_days
            archive_cutoff = (
                now - timedelta(days=policy.archive_after_days)
                if policy.archive_after_days is not None
                else None
            )
            delete_cutoff = now - timedelta(days=delete_days)
            candidates = await handler.list_candidates(
                policy=policy,
                archive_cutoff=archive_cutoff,
                delete_cutoff=delete_cutoff,
                limit=remaining,
            )
            scanned += len(candidates)
            remaining -= len(candidates)
            for candidate in candidates:
                if policy.legal_hold_enabled or candidate.legal_hold:
                    legal_hold_skipped += 1
                    continue
                if candidate.sole_copy and not self.allow_sole_copy_deletion:
                    warnings.append(
                        "A sole-copy record was retained pending an explicit policy."
                    )
                    continue
                eligible += 1
                if dry_run:
                    continue
                if (
                    archive_cutoff is not None
                    and handler.supports_archive
                    and not candidate.archived
                    and candidate.created_at <= archive_cutoff
                ):
                    await handler.archive(candidate)
                    archived += 1
                if candidate.created_at > delete_cutoff:
                    continue
                if handler.supports_soft_delete and not candidate.soft_deleted:
                    await handler.soft_delete(candidate)
                    soft_deleted += 1
                else:
                    await handler.permanently_delete(candidate)
                    permanently_deleted += 1
        summary = RetentionRunResponse(
            entity_type=entity_type,
            dry_run=dry_run,
            scanned_count=scanned,
            eligible_count=eligible,
            archived_count=archived,
            soft_deleted_count=soft_deleted,
            permanently_deleted_count=permanently_deleted,
            legal_hold_skipped_count=legal_hold_skipped,
            warnings=list(dict.fromkeys(warnings)),
        )
        if not dry_run:
            if self.audit_sink is not None:
                await self.audit_sink.record_summary(summary)
            await self.audit.create(
                action=AuditAction.EXECUTE_RETENTION_CLEANUP,
                user_id=self.actor_id,
                entity_type="RetentionCleanup",
                description="Data retention cleanup executed.",
                new_values=summary.model_dump(
                    mode="json",
                    by_alias=True,
                ),
            )
            await self.session.commit()
        else:
            await self.session.rollback()
        return summary
