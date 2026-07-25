"""Append-only audit-log persistence."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.models.audit_log import AuditLog


class AuditLogRepository:
    """Create security audit records without accepting secrets or tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        action: AuditAction,
        description: str,
        user_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_values_json=old_values,
            new_values_json=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(audit_log)
        await self._session.flush()
        return audit_log
