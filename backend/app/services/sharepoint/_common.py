"""Shared SharePoint access, errors, pagination, and optional audit bridge."""

from __future__ import annotations

from http import HTTPStatus
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, get_permissions
from app.core.exceptions import ApplicationError, AuthorizationError
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.schemas.common import ErrorDetail
from app.services.auth.auth_service import RequestMetadata


def sharepoint_error(
    message: str,
    *,
    code: str,
    status_code: int = HTTPStatus.BAD_REQUEST,
    title: str = "SharePoint operation failed.",
    field: str | None = None,
) -> ApplicationError:
    return ApplicationError(
        title,
        status_code=status_code,
        errors=[ErrorDetail(field=field, message=message, code=code)],
    )


def total_pages(total: int, page_size: int) -> int:
    return ceil(total / page_size) if total else 0


class SharePointAccessPolicy:
    def __init__(self, user: User) -> None:
        self.user = user
        self.permissions = set(
            get_permissions(
                user.role,
                is_superuser=user.is_superuser,
            )
        )

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise AuthorizationError()

    @property
    def view_all_departments(self) -> bool:
        return "sharepoint:view_all_departments" in self.permissions

    def department_ids(self) -> list[UUID] | None:
        if self.view_all_departments:
            return None
        if self.user.department_id is None:
            raise AuthorizationError(
                "A department assignment is required for SharePoint access."
            )
        return [self.user.department_id]

    def ensure_department(self, department_id: UUID) -> None:
        if (
            not self.view_all_departments
            and self.user.department_id != department_id
        ):
            raise AuthorizationError(
                "This SharePoint resource is outside your department scope."
            )


class SharePointServiceBase:
    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        self.session = session
        self.user = user
        self.metadata = metadata
        self.policy = SharePointAccessPolicy(user)
        self.audits = AuditLogRepository(session)

    async def audit_if_registered(
        self,
        action_name: str,
        *,
        entity_type: str,
        entity_id: UUID | None,
        description: str,
        values: dict[str, Any] | None = None,
    ) -> None:
        """Audit once root authorization integration registers Phase 10 names."""

        action = getattr(AuditAction, action_name, None)
        if action is None:
            return
        await self.audits.create(
            user_id=self.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            new_values=values,
            ip_address=self.metadata.ip_address,
            user_agent=self.metadata.user_agent,
        )
