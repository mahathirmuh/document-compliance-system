"""Idempotent cron-driven creation and dispatch of SharePoint sync jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from celery.schedules import crontab

from app.core.config import Settings
from app.database.session import AsyncSessionFactory
from app.models.sharepoint_enums import (
    SharePointSyncJobStatus,
    SyncJobType,
)
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.utils.datetime import utc_now


class SharePointScheduledSyncService:
    """Create at most one active scheduled job for each due profile."""

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory=AsyncSessionFactory,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    async def dispatch_due(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, int]:
        current = self._aware(now or utc_now())
        if not bool(
            getattr(self.settings, "sharepoint_sync_enabled", False)
        ):
            return {
                "created": 0,
                "dispatched": 0,
                "skipped": 0,
                "invalid": 0,
                "failed": 0,
            }

        pending: list[UUID] = []
        created = skipped = invalid = 0
        async with self.session_factory() as session:
            repository = SharePointSyncRepository(session)
            profiles = await repository.scheduled_profiles_for_update()
            for profile in profiles:
                expression = (profile.sync_schedule or "").strip()
                if not expression or expression.casefold() == "manual":
                    skipped += 1
                    continue
                active = await repository.active_job(profile.id)
                if active is not None:
                    summary = dict(active.result_summary_json or {})
                    if (
                        active.status is SharePointSyncJobStatus.QUEUED
                        and summary.get("scheduleDispatchState")
                        == "PENDING"
                    ):
                        pending.append(active.id)
                    else:
                        skipped += 1
                    continue
                latest = await repository.latest_scheduled_job(profile.id)
                last_run = (
                    latest.requested_at
                    if latest is not None
                    else profile.created_at
                )
                try:
                    due = self._is_due(
                        expression,
                        last_run_at=self._aware(last_run),
                        now=current,
                    )
                except (KeyError, TypeError, ValueError):
                    invalid += 1
                    continue
                if not due:
                    skipped += 1
                    continue
                job = SharePointSyncJob(
                    sync_profile_id=profile.id,
                    sharepoint_connection_id=(
                        profile.sharepoint_connection_id
                    ),
                    job_type=(
                        SyncJobType.SCHEDULED_INCREMENTAL
                        if profile.delta_sync_enabled
                        else SyncJobType.SCHEDULED_FULL
                    ),
                    direction=profile.direction,
                    status=SharePointSyncJobStatus.QUEUED,
                    progress=0,
                    current_stage="Queued by schedule",
                    scope_json={
                        "scheduled": True,
                        "schedule": expression,
                    },
                    requested_by=None,
                    maximum_attempts=max(
                        1,
                        int(
                            getattr(
                                self.settings,
                                "sharepoint_max_retries",
                                3,
                            )
                        )
                        + 1,
                    ),
                    result_summary_json={
                        "scheduleDispatchState": "PENDING",
                    },
                )
                await repository.add_job(job)
                pending.append(job.id)
                created += 1
            await session.commit()

        dispatched = failed = 0
        for job_id in pending:
            try:
                task_id = self._dispatch(job_id)
            except Exception:  # noqa: BLE001 - broker boundary
                await self._mark_dispatch_failed(job_id)
                failed += 1
                continue
            await self._mark_dispatched(
                job_id,
                task_id=task_id,
                dispatched_at=current,
            )
            dispatched += 1
        return {
            "created": created,
            "dispatched": dispatched,
            "skipped": skipped,
            "invalid": invalid,
            "failed": failed,
        }

    def _dispatch(self, job_id: UUID) -> str:
        from app.workers.sharepoint_tasks import (
            process_sharepoint_sync_job,
        )

        task_id = f"sharepoint-sync-job-{job_id}"
        process_sharepoint_sync_job.apply_async(
            args=[str(job_id)],
            queue=self.settings.sharepoint_queue_name,
            task_id=task_id,
        )
        return task_id

    async def _mark_dispatched(
        self,
        job_id: UUID,
        *,
        task_id: str,
        dispatched_at: datetime,
    ) -> None:
        async with self.session_factory() as session:
            job = await SharePointSyncRepository(session).get_job(
                job_id,
                for_update=True,
            )
            if job is None:
                return
            summary = dict(job.result_summary_json or {})
            summary.update(
                {
                    "scheduleDispatchState": "DISPATCHED",
                    "scheduleTaskId": task_id,
                    "scheduleDispatchedAt": dispatched_at.isoformat(),
                }
            )
            job.result_summary_json = summary
            await session.commit()

    async def _mark_dispatch_failed(self, job_id: UUID) -> None:
        async with self.session_factory() as session:
            job = await SharePointSyncRepository(session).get_job(
                job_id,
                for_update=True,
            )
            if (
                job is None
                or job.status is not SharePointSyncJobStatus.QUEUED
            ):
                return
            job.status = SharePointSyncJobStatus.FAILED
            job.progress = 0
            job.current_stage = "Scheduled dispatch failed"
            job.failed_at = utc_now()
            job.error_code = "SHAREPOINT_WORKER_UNAVAILABLE"
            job.error_message = (
                "The scheduled SharePoint job could not be dispatched."
            )
            await session.commit()

    @staticmethod
    def _is_due(
        expression: str,
        *,
        last_run_at: datetime,
        now: datetime,
    ) -> bool:
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError(
                "SharePoint sync schedule must be a five-field cron expression."
            )
        schedule = crontab(
            minute=fields[0],
            hour=fields[1],
            day_of_month=fields[2],
            month_of_year=fields[3],
            day_of_week=fields[4],
            nowfun=lambda: now,
        )
        return bool(schedule.is_due(last_run_at).is_due)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return (
            value.replace(tzinfo=UTC)
            if value.tzinfo is None
            else value.astimezone(UTC)
        )
