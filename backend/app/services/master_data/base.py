"""Shared transaction, error, pagination, and audit helpers."""

from http import HTTPStatus
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.core.exceptions import ApplicationError
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.schemas.common import ErrorDetail
from app.services.auth.auth_service import RequestMetadata


def not_found(entity_name: str) -> ApplicationError:
    return ApplicationError(
        f"{entity_name} was not found.",
        status_code=HTTPStatus.NOT_FOUND,
        errors=[
            ErrorDetail(
                field=None,
                message=f"{entity_name} does not exist or was deleted.",
            )
        ],
    )


def conflict(
    message: str,
    *,
    field: str | None = None,
    title: str = "Master data could not be saved.",
) -> ApplicationError:
    return ApplicationError(
        title,
        status_code=HTTPStatus.CONFLICT,
        errors=[ErrorDetail(field=field, message=message)],
    )


def business_error(
    message: str,
    *,
    field: str | None = None,
) -> ApplicationError:
    return ApplicationError(
        "Master data validation failed.",
        status_code=HTTPStatus.BAD_REQUEST,
        errors=[ErrorDetail(field=field, message=message)],
    )


def audit_dump(response: BaseModel) -> dict[str, Any]:
    return response.model_dump(mode="json", by_alias=True)


class MasterDataServiceBase:
    """Own write transactions and common audit metadata."""

    entity_name: str
    entity_type: str

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

    async def commit_audited(
        self,
        *,
        action: AuditAction,
        entity_id: UUID | None,
        description: str,
        old_values: dict[str, Any] | None,
        new_values: dict[str, Any] | None,
        duplicate_message: str,
        duplicate_field: str | None = "code",
    ) -> None:
        try:
            await self.audit_logs.create(
                user_id=self.user.id,
                action=action,
                entity_type=self.entity_type,
                entity_id=entity_id,
                description=description,
                old_values=old_values,
                new_values=new_values,
                ip_address=self.metadata.ip_address,
                user_agent=self.metadata.user_agent,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise conflict(
                duplicate_message,
                field=duplicate_field,
                title=f"{self.entity_name} could not be saved.",
            ) from exc

    async def rollback_conflict(
        self,
        exc: IntegrityError,
        *,
        message: str,
        field: str | None = "code",
    ) -> None:
        await self.session.rollback()
        raise conflict(
            message,
            field=field,
            title=f"{self.entity_name} could not be saved.",
        ) from exc

    @staticmethod
    def total_pages(total: int, page_size: int) -> int:
        return (total + page_size - 1) // page_size if total else 0

