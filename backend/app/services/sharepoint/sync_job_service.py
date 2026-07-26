"""Scoped sync profile and job lifecycle, dispatch, cancel, and retry."""

from __future__ import annotations

from http import HTTPStatus
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.sharepoint_enums import (
    ACTIVE_SYNC_JOB_STATUSES,
    SharePointSyncJobStatus,
)
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.models.sharepoint_sync_profile import SharePointSyncProfile
from app.models.user import User
from app.repositories.sharepoint_connection_repository import (
    SharePointConnectionRepository,
)
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.schemas.sharepoint_sync import (
    SharePointSyncJobCreateRequest,
    SharePointSyncJobListResponse,
    SharePointSyncJobResponse,
    SharePointSyncProfileCreateRequest,
    SharePointSyncProfileListResponse,
    SharePointSyncProfileResponse,
    SharePointSyncProfileUpdateRequest,
)
from app.services.auth.auth_service import RequestMetadata
from app.services.sharepoint._common import (
    SharePointServiceBase,
    sharepoint_error,
    total_pages,
)
from app.utils.datetime import utc_now


class SharePointSyncJobService(SharePointServiceBase):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.repository = SharePointSyncRepository(session)
        self.connections = SharePointConnectionRepository(session)

    async def list_profiles(
        self,
        *,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> SharePointSyncProfileListResponse:
        items, total = await self.repository.list_profiles(
            department_ids=self.policy.department_ids(),
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return SharePointSyncProfileListResponse(
            items=[
                SharePointSyncProfileResponse.model_validate(item)
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages(total, page_size),
        )

    async def get_profile(
        self,
        profile_id: UUID,
    ) -> SharePointSyncProfileResponse:
        profile = await self._profile(profile_id)
        self._scope_profile(profile)
        return SharePointSyncProfileResponse.model_validate(profile)

    async def create_profile(
        self,
        payload: SharePointSyncProfileCreateRequest,
    ) -> SharePointSyncProfileResponse:
        if (
            await self.connections.get_by_id(
                payload.sharepoint_connection_id
            )
            is None
        ):
            raise sharepoint_error(
                "SharePoint connection was not found.",
                code="SHAREPOINT_CONNECTION_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        if payload.department_id is not None:
            self.policy.ensure_department(payload.department_id)
        profile = SharePointSyncProfile(
            **payload.model_dump(),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        await self.repository.add_profile(profile)
        await self.audit_if_registered(
            "CREATE_SYNC_PROFILE",
            entity_type="SharePointSyncProfile",
            entity_id=profile.id,
            description="SharePoint sync profile created.",
            values={
                "connectionId": str(profile.sharepoint_connection_id),
                "direction": profile.direction.value,
                "conflictPolicy": profile.conflict_policy.value,
                "deletePolicy": profile.delete_policy.value,
            },
        )
        await self.session.commit()
        return SharePointSyncProfileResponse.model_validate(profile)

    async def update_profile(
        self,
        profile_id: UUID,
        payload: SharePointSyncProfileUpdateRequest,
    ) -> SharePointSyncProfileResponse:
        profile = await self._profile(profile_id, for_update=True)
        self._scope_profile(profile)
        if payload.department_id is not None:
            self.policy.ensure_department(payload.department_id)
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
        profile.updated_by = self.user.id
        await self.audit_if_registered(
            "UPDATE_SYNC_PROFILE",
            entity_type="SharePointSyncProfile",
            entity_id=profile.id,
            description="SharePoint sync profile updated.",
        )
        await self.session.commit()
        return SharePointSyncProfileResponse.model_validate(profile)

    async def set_profile_active(
        self,
        profile_id: UUID,
        *,
        active: bool,
    ) -> SharePointSyncProfileResponse:
        profile = await self._profile(profile_id, for_update=True)
        self._scope_profile(profile)
        profile.is_active = active
        profile.updated_by = self.user.id
        await self.audit_if_registered(
            (
                "ACTIVATE_SYNC_PROFILE"
                if active
                else "DEACTIVATE_SYNC_PROFILE"
            ),
            entity_type="SharePointSyncProfile",
            entity_id=profile.id,
            description=(
                "SharePoint sync profile activated."
                if active
                else "SharePoint sync profile deactivated."
            ),
        )
        await self.session.commit()
        return SharePointSyncProfileResponse.model_validate(profile)

    async def queue_job(
        self,
        payload: SharePointSyncJobCreateRequest,
    ) -> SharePointSyncJobResponse:
        profile = await self._profile(payload.sync_profile_id)
        self._scope_profile(profile)
        if not profile.is_active:
            raise sharepoint_error(
                "SharePoint sync profile is inactive.",
                code="SHAREPOINT_SYNC_FAILED",
            )
        if await self.repository.active_job(profile.id) is not None:
            raise sharepoint_error(
                "A SharePoint sync job is already active.",
                code="SHAREPOINT_SYNC_ACTIVE",
                status_code=HTTPStatus.CONFLICT,
            )
        job = SharePointSyncJob(
            sync_profile_id=profile.id,
            sharepoint_connection_id=profile.sharepoint_connection_id,
            job_type=payload.job_type,
            direction=payload.direction or profile.direction,
            status=SharePointSyncJobStatus.QUEUED,
            progress=0,
            current_stage="Queued",
            scope_json=payload.scope,
            requested_by=self.user.id,
            maximum_attempts=max(
                1,
                int(getattr(self.settings, "sharepoint_max_retries", 3))
                + 1,
            ),
        )
        await self.repository.add_job(job)
        await self.audit_if_registered(
            "QUEUE_SHAREPOINT_SYNC",
            entity_type="SharePointSyncJob",
            entity_id=job.id,
            description="SharePoint sync job queued.",
            values={
                "profileId": str(profile.id),
                "jobType": job.job_type.value,
                "direction": job.direction.value,
            },
        )
        await self.session.commit()
        await self._dispatch(job)
        return SharePointSyncJobResponse.model_validate(job)

    async def list_jobs(
        self,
        *,
        statuses: list[SharePointSyncJobStatus] | None,
        page: int,
        page_size: int,
    ) -> SharePointSyncJobListResponse:
        items, total = await self.repository.list_jobs(
            department_ids=self.policy.department_ids(),
            statuses=statuses,
            page=page,
            page_size=page_size,
        )
        return SharePointSyncJobListResponse(
            items=[
                SharePointSyncJobResponse.model_validate(item)
                for item in items
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages(total, page_size),
        )

    async def get_job(
        self,
        job_id: UUID,
    ) -> SharePointSyncJobResponse:
        job = await self._job(job_id)
        return SharePointSyncJobResponse.model_validate(job)

    async def cancel(
        self,
        job_id: UUID,
    ) -> SharePointSyncJobResponse:
        job = await self._job(job_id, for_update=True)
        if job.status not in ACTIVE_SYNC_JOB_STATUSES:
            raise sharepoint_error(
                "Only an active SharePoint sync job can be cancelled.",
                code="SHAREPOINT_SYNC_FAILED",
                status_code=HTTPStatus.CONFLICT,
            )
        if job.status is SharePointSyncJobStatus.QUEUED:
            job.status = SharePointSyncJobStatus.CANCELLED
            job.cancelled_at = utc_now()
            job.progress = 100
            job.current_stage = "Cancelled"
        else:
            job.status = SharePointSyncJobStatus.CANCEL_REQUESTED
            job.current_stage = "Cancellation requested"
        await self.audit_if_registered(
            "CANCEL_SHAREPOINT_SYNC",
            entity_type="SharePointSyncJob",
            entity_id=job.id,
            description="SharePoint sync cancellation requested.",
        )
        await self.session.commit()
        return SharePointSyncJobResponse.model_validate(job)

    async def retry(
        self,
        job_id: UUID,
    ) -> SharePointSyncJobResponse:
        original = await self._job(job_id, for_update=True)
        if original.status not in {
            SharePointSyncJobStatus.FAILED,
            SharePointSyncJobStatus.PARTIALLY_COMPLETED,
            SharePointSyncJobStatus.DEAD_LETTER,
            SharePointSyncJobStatus.CANCELLED,
        }:
            raise sharepoint_error(
                "This SharePoint sync job is not retryable.",
                code="SHAREPOINT_SYNC_FAILED",
                status_code=HTTPStatus.CONFLICT,
            )
        original.status = SharePointSyncJobStatus.QUEUED
        original.progress = 0
        original.current_stage = "Queued for retry"
        original.error_code = None
        original.error_message = None
        original.failed_at = None
        original.cancelled_at = None
        original.attempt_number = min(
            original.maximum_attempts,
            original.attempt_number + 1,
        )
        await self.audit_if_registered(
            "RETRY_SHAREPOINT_SYNC",
            entity_type="SharePointSyncJob",
            entity_id=original.id,
            description="SharePoint sync job queued for retry.",
        )
        await self.session.commit()
        await self._dispatch(original)
        return SharePointSyncJobResponse.model_validate(original)

    async def reset_delta(
        self,
        profile_id: UUID,
        *,
        reason: str,
    ) -> bool:
        profile = await self._profile(profile_id)
        self._scope_profile(profile)
        # Delta state may cover multiple folder IDs.
        from sqlalchemy import select

        from app.models.sharepoint_delta_state import SharePointDeltaState

        states = list(
            await self.session.scalars(
                select(SharePointDeltaState).where(
                    SharePointDeltaState.sync_profile_id == profile.id,
                    SharePointDeltaState.is_valid.is_(True),
                )
            )
        )
        now = utc_now()
        for state in states:
            state.is_valid = False
            state.invalidated_at = now
            state.invalidation_reason = reason.strip()
        await self.audit_if_registered(
            "RESET_SHAREPOINT_DELTA",
            entity_type="SharePointSyncProfile",
            entity_id=profile.id,
            description="SharePoint delta state reset.",
            values={"reason": reason.strip(), "statesInvalidated": len(states)},
        )
        await self.session.commit()
        return bool(states)

    async def _dispatch(self, job: SharePointSyncJob) -> None:
        try:
            from app.workers.sharepoint_tasks import (
                process_sharepoint_sync_job,
            )

            process_sharepoint_sync_job.apply_async(
                args=[str(job.id)],
                queue=str(
                    getattr(
                        self.settings,
                        "sharepoint_queue_name",
                        "sharepoint",
                    )
                ),
                task_id=str(uuid4()),
            )
        except Exception as exc:
            await self.session.rollback()
            job = await self.repository.get_job(job.id, for_update=True)
            if job is not None:
                job.status = SharePointSyncJobStatus.FAILED
                job.failed_at = utc_now()
                job.error_code = "SHAREPOINT_WORKER_UNAVAILABLE"
                job.error_message = (
                    "The SharePoint worker could not accept this job."
                )
                await self.session.commit()
            raise sharepoint_error(
                "The SharePoint worker is temporarily unavailable.",
                code="SHAREPOINT_SYNC_FAILED",
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc

    async def _profile(
        self,
        profile_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointSyncProfile:
        profile = await self.repository.get_profile(
            profile_id,
            for_update=for_update,
        )
        if profile is None:
            raise sharepoint_error(
                "SharePoint sync profile was not found.",
                code="SHAREPOINT_SYNC_FAILED",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return profile

    async def _job(
        self,
        job_id: UUID,
        *,
        for_update: bool = False,
    ) -> SharePointSyncJob:
        job = await self.repository.get_job(
            job_id,
            department_ids=self.policy.department_ids(),
            for_update=for_update,
        )
        if job is None:
            raise sharepoint_error(
                "SharePoint sync job was not found.",
                code="SHAREPOINT_SYNC_FAILED",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return job

    def _scope_profile(self, profile: SharePointSyncProfile) -> None:
        if profile.department_id is not None:
            self.policy.ensure_department(profile.department_id)
        elif not self.policy.view_all_departments:
            raise sharepoint_error(
                "Global sync profiles require all-department access.",
                code="SHAREPOINT_PERMISSION_DENIED",
                status_code=HTTPStatus.FORBIDDEN,
            )
