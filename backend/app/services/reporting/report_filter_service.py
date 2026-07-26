"""Validate report filters and enforce department scope server-side."""

from __future__ import annotations

from uuid import UUID

from app.core.authorization import Permission, has_permission
from app.core.exceptions import AuthorizationError
from app.models.user import User
from app.schemas.advanced_reporting import AdvancedReportFilters


class ReportFilterService:
    def __init__(self, user: User) -> None:
        self.user = user

    def validate(
        self, filters: AdvancedReportFilters
    ) -> AdvancedReportFilters:
        """Return a canonical scope-safe copy."""

        requested = list(dict.fromkeys(filters.department_ids))
        if self._can_cross_departments():
            return filters.model_copy(
                update={"department_ids": requested}
            )
        if self.user.department_id is None:
            raise AuthorizationError(
                "A department must be assigned before reporting."
            )
        if requested and requested != [self.user.department_id]:
            raise AuthorizationError(
                "Report filters are outside your department scope."
            )
        return filters.model_copy(
            update={"department_ids": [self.user.department_id]}
        )

    def scope_department_id(
        self, filters: AdvancedReportFilters
    ) -> UUID | None:
        if self._can_cross_departments():
            return (
                filters.department_ids[0]
                if len(filters.department_ids) == 1
                else None
            )
        return self.user.department_id

    def query_scope(self) -> list[UUID] | None:
        if self._can_cross_departments():
            return None
        return [self.user.department_id] if self.user.department_id else []

    def _can_cross_departments(self) -> bool:
        return (
            self.user.is_superuser
            or has_permission(
                self.user.role,
                Permission.COMPLIANCE_VIEW_ALL_DEPARTMENTS,
                is_superuser=self.user.is_superuser,
            )
            or has_permission(
                self.user.role,
                Permission.SIMILARITY_VIEW_ALL_DEPARTMENTS,
                is_superuser=self.user.is_superuser,
            )
            or has_permission(
                self.user.role,
                Permission.REVISION_COMPARISON_VIEW_ALL_DEPARTMENTS,
                is_superuser=self.user.is_superuser,
            )
        )
