"""Shared glossary authorization, audit, and response helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction, UserRole
from app.core.exceptions import ApplicationError
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.schemas.common import ErrorDetail
from app.services.auth.auth_service import RequestMetadata

_CROSS_DEPARTMENT_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.DOCUMENT_CONTROLLER,
    UserRole.AUDITOR,
}


def visible_department_ids(user: User) -> list[UUID] | None:
    """Return ``None`` for cross-department users, otherwise own scope."""

    if user.is_superuser or user.role in _CROSS_DEPARTMENT_ROLES:
        return None
    return [user.department_id] if user.department_id is not None else []


def glossary_not_found(entity: str) -> ApplicationError:
    return ApplicationError(
        f"{entity} was not found.",
        status_code=404,
        errors=[
            ErrorDetail(
                field=None,
                message=(
                    f"{entity} does not exist or is outside your scope."
                ),
            )
        ],
    )


def glossary_error(
    message: str,
    *,
    field: str | None = None,
    status_code: int = 400,
) -> ApplicationError:
    return ApplicationError(
        "Glossary validation failed.",
        status_code=status_code,
        errors=[ErrorDetail(field=field, message=message)],
    )


class GlossaryServiceBase:
    """Own glossary write transactions and append-only audit metadata."""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        metadata: RequestMetadata,
    ) -> None:
        self.session = session
        self.user = user
        self.metadata = metadata
        self.audit_logs = AuditLogRepository(session)

    @property
    def department_ids(self) -> list[UUID] | None:
        return visible_department_ids(self.user)

    async def audit(
        self,
        *,
        action: AuditAction,
        entity_type: str,
        entity_id: UUID | None,
        description: str,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
    ) -> None:
        await self.audit_logs.create(
            user_id=self.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=self.metadata.ip_address,
            user_agent=self.metadata.user_agent,
        )

    async def commit_or_conflict(
        self,
        *,
        message: str,
        field: str | None = None,
    ) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise glossary_error(
                message,
                field=field,
                status_code=409,
            ) from exc

    @staticmethod
    def total_pages(total: int, page_size: int) -> int:
        return (total + page_size - 1) // page_size if total else 0
