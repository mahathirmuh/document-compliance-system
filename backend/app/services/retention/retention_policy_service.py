"""Administration service for approved retention policies."""

from __future__ import annotations

from http import HTTPStatus
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.data_retention_policy import (
    DataRetentionPolicy,
    RetentionEntityType,
)
from app.repositories.audit_log import AuditLogRepository
from app.repositories.data_retention_policy_repository import (
    DataRetentionPolicyRepository,
)
from app.schemas.retention import (
    RetentionPolicyCreateRequest,
    RetentionPolicyListResponse,
    RetentionPolicyResponse,
    RetentionPolicyUpdateRequest,
)
from app.services.notification.errors import notification_error


class RetentionPolicyService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
    ) -> None:
        self.session = session
        self.actor_id = actor_id
        self.repository = DataRetentionPolicyRepository(session)
        self.audit = AuditLogRepository(session)

    async def list(
        self,
        *,
        entity_type: RetentionEntityType | None,
        include_inactive: bool,
        page: int,
        page_size: int,
    ) -> RetentionPolicyListResponse:
        rows, total = await self.repository.list_page(
            entity_type=entity_type,
            include_inactive=include_inactive,
            page=page,
            page_size=page_size,
        )
        return RetentionPolicyListResponse(
            items=[RetentionPolicyResponse.model_validate(item) for item in rows],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    async def create(
        self,
        payload: RetentionPolicyCreateRequest,
    ) -> RetentionPolicyResponse:
        policy = DataRetentionPolicy(
            **payload.model_dump(),
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        await self.repository.add(policy)
        await self.audit.create(
            action=AuditAction.CREATE_RETENTION_POLICY,
            user_id=self.actor_id,
            entity_type="DataRetentionPolicy",
            entity_id=policy.id,
            description="Data retention policy created.",
            new_values=self._audit_values(policy),
        )
        await self.session.commit()
        await self.session.refresh(policy)
        return RetentionPolicyResponse.model_validate(policy)

    async def update(
        self,
        policy_id: UUID,
        payload: RetentionPolicyUpdateRequest,
    ) -> RetentionPolicyResponse:
        policy = await self._get(policy_id, for_update=True)
        old_values = self._audit_values(policy)
        values = payload.model_dump(exclude_unset=True)
        archive_after = values.get(
            "archive_after_days",
            policy.archive_after_days,
        )
        delete_after = values.get(
            "delete_after_days",
            policy.delete_after_days,
        )
        if (
            archive_after is not None
            and delete_after is not None
            and delete_after < archive_after
        ):
            raise notification_error(
                "Delete threshold cannot precede archive threshold.",
                code="RETENTION_POLICY_INVALID",
            )
        for field, value in values.items():
            setattr(policy, field, value)
        policy.updated_by = self.actor_id
        await self.audit.create(
            action=AuditAction.UPDATE_RETENTION_POLICY,
            user_id=self.actor_id,
            entity_type="DataRetentionPolicy",
            entity_id=policy.id,
            description="Data retention policy updated.",
            old_values=old_values,
            new_values=self._audit_values(policy),
        )
        await self.session.commit()
        await self.session.refresh(policy)
        return RetentionPolicyResponse.model_validate(policy)

    async def _get(
        self,
        policy_id: UUID,
        *,
        for_update: bool,
    ) -> DataRetentionPolicy:
        policy = await self.repository.get_by_id(
            policy_id,
            for_update=for_update,
        )
        if policy is None:
            raise notification_error(
                "Retention policy was not found.",
                code="RETENTION_POLICY_NOT_FOUND",
                status_code=HTTPStatus.NOT_FOUND,
            )
        return policy

    @staticmethod
    def _audit_values(policy: DataRetentionPolicy) -> dict[str, object]:
        return {
            "name": policy.name,
            "entityType": policy.entity_type.value,
            "scopeType": policy.scope_type.value,
            "departmentId": (
                str(policy.department_id) if policy.department_id else None
            ),
            "documentTypeId": (
                str(policy.document_type_id) if policy.document_type_id else None
            ),
            "retentionDays": policy.retention_days,
            "archiveAfterDays": policy.archive_after_days,
            "deleteAfterDays": policy.delete_after_days,
            "legalHoldEnabled": policy.legal_hold_enabled,
            "isActive": policy.is_active,
        }
