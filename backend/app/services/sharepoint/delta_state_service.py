"""Persist Graph delta links only after a successful sync transaction."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharepoint_delta_state import SharePointDeltaState
from app.models.sharepoint_enums import SharePointSyncJobStatus
from app.models.sharepoint_sync_job import SharePointSyncJob
from app.repositories.sharepoint_sync_repository import (
    SharePointSyncRepository,
)
from app.utils.datetime import utc_now


class IntegrationStateCipher(Protocol):
    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


class SharePointDeltaStateService:
    def __init__(
        self,
        session: AsyncSession,
        cipher: IntegrationStateCipher,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.repository = SharePointSyncRepository(session)

    async def load(
        self,
        *,
        profile_id: UUID,
        drive_id: str,
        folder_item_id: str | None,
    ) -> str | None:
        state = await self.repository.get_delta_state(
            profile_id=profile_id,
            drive_id=drive_id,
            folder_item_id=folder_item_id,
        )
        if state is None or not state.is_valid:
            return None
        return self.cipher.decrypt(state.delta_link_encrypted)

    async def commit_after_success(
        self,
        *,
        job: SharePointSyncJob,
        drive_id: str,
        folder_item_id: str | None,
        delta_link: str,
        expires_at: datetime | None = None,
    ) -> SharePointDeltaState:
        if job.status is not SharePointSyncJobStatus.COMPLETED:
            raise ValueError(
                "Delta state can only advance after a completed sync job."
            )
        token_hash = hashlib.sha256(
            delta_link.encode("utf-8")
        ).hexdigest()
        encrypted = self.cipher.encrypt(delta_link)
        if encrypted == delta_link:
            raise ValueError("Integration state cipher returned plaintext.")
        state = await self.repository.get_delta_state(
            profile_id=job.sync_profile_id,
            drive_id=drive_id,
            folder_item_id=folder_item_id,
            for_update=True,
        )
        if state is None:
            state = SharePointDeltaState(
                sync_profile_id=job.sync_profile_id,
                drive_id=drive_id,
                folder_item_id=folder_item_id,
                delta_link_encrypted=encrypted,
                delta_token_hash=token_hash,
            )
            await self.repository.add_delta_state(state)
        else:
            state.delta_link_encrypted = encrypted
            state.delta_token_hash = token_hash
        state.last_successful_sync_job_id = job.id
        state.last_synced_at = utc_now()
        state.expires_at = expires_at
        state.is_valid = True
        state.invalidated_at = None
        state.invalidation_reason = None
        job.delta_token_after = token_hash
        await self.session.flush()
        return state

    async def invalidate(
        self,
        *,
        profile_id: UUID,
        drive_id: str,
        folder_item_id: str | None,
        reason: str,
    ) -> bool:
        state = await self.repository.get_delta_state(
            profile_id=profile_id,
            drive_id=drive_id,
            folder_item_id=folder_item_id,
            for_update=True,
        )
        if state is None:
            return False
        state.is_valid = False
        state.invalidated_at = utc_now()
        state.invalidation_reason = reason.strip()
        await self.session.flush()
        return True
