"""Canonical roles, permissions, and auditable action names."""

from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping


class UserRole(str, Enum):
    """Roles assignable to an application user."""

    SUPER_ADMIN = "SUPER_ADMIN"
    DOCUMENT_CONTROLLER = "DOCUMENT_CONTROLLER"
    REVIEWER = "REVIEWER"
    DEPARTMENT_USER = "DEPARTMENT_USER"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class Permission(str, Enum):
    """Atomic capabilities from the Phase 2 authorization contract."""

    DASHBOARD_VIEW = "dashboard:view"
    DOCUMENTS_VIEW = "documents:view"
    DOCUMENTS_CREATE = "documents:create"
    DOCUMENTS_UPDATE = "documents:update"
    DOCUMENTS_ARCHIVE = "documents:archive"
    DOCUMENTS_RESTORE = "documents:restore"
    DOCUMENTS_EXPORT = "documents:export"
    DOCUMENTS_IMPORT = "documents:import"
    DOCUMENTS_VIEW_ALL_DEPARTMENTS = "documents:view_all_departments"
    DOCUMENTS_MANAGE_REVISIONS = "documents:manage_revisions"
    DOCUMENTS_DELETE = "documents:delete"
    DOCUMENTS_VALIDATE = "documents:validate"
    DOCUMENTS_ASSIGN_REVIEWER = "documents:assign_reviewer"
    FINDINGS_VIEW = "findings:view"
    FINDINGS_UPDATE = "findings:update"
    FINDINGS_RESOLVE = "findings:resolve"
    MASTER_DATA_VIEW = "master_data:view"
    MASTER_DATA_CREATE = "master_data:create"
    MASTER_DATA_UPDATE = "master_data:update"
    MASTER_DATA_DELETE = "master_data:delete"
    REPORTS_VIEW = "reports:view"
    REPORTS_EXPORT = "reports:export"
    USERS_VIEW = "users:view"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DISABLE = "users:disable"
    AUDIT_LOGS_VIEW = "audit_logs:view"
    SETTINGS_VIEW = "settings:view"
    SETTINGS_UPDATE = "settings:update"


class AuditAction(str, Enum):
    """Security and business events stored in the append-only audit log."""

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    CREATE_DEPARTMENT = "CREATE_DEPARTMENT"
    UPDATE_DEPARTMENT = "UPDATE_DEPARTMENT"
    ACTIVATE_DEPARTMENT = "ACTIVATE_DEPARTMENT"
    DEACTIVATE_DEPARTMENT = "DEACTIVATE_DEPARTMENT"
    CREATE_SECTION = "CREATE_SECTION"
    UPDATE_SECTION = "UPDATE_SECTION"
    ACTIVATE_SECTION = "ACTIVATE_SECTION"
    DEACTIVATE_SECTION = "DEACTIVATE_SECTION"
    CREATE_DOCUMENT_TYPE = "CREATE_DOCUMENT_TYPE"
    UPDATE_DOCUMENT_TYPE = "UPDATE_DOCUMENT_TYPE"
    ACTIVATE_DOCUMENT_TYPE = "ACTIVATE_DOCUMENT_TYPE"
    DEACTIVATE_DOCUMENT_TYPE = "DEACTIVATE_DOCUMENT_TYPE"
    CREATE_DOCUMENT_STATUS = "CREATE_DOCUMENT_STATUS"
    UPDATE_DOCUMENT_STATUS = "UPDATE_DOCUMENT_STATUS"
    ACTIVATE_DOCUMENT_STATUS = "ACTIVATE_DOCUMENT_STATUS"
    DEACTIVATE_DOCUMENT_STATUS = "DEACTIVATE_DOCUMENT_STATUS"
    CREATE_VALIDATION_RULE = "CREATE_VALIDATION_RULE"
    UPDATE_VALIDATION_RULE = "UPDATE_VALIDATION_RULE"
    ACTIVATE_VALIDATION_RULE = "ACTIVATE_VALIDATION_RULE"
    DEACTIVATE_VALIDATION_RULE = "DEACTIVATE_VALIDATION_RULE"
    SET_DEFAULT_VALIDATION_RULE = "SET_DEFAULT_VALIDATION_RULE"
    IMPORT_MASTER_DATA = "IMPORT_MASTER_DATA"
    EXPORT_MASTER_DATA = "EXPORT_MASTER_DATA"
    CREATE_DOCUMENT = "CREATE_DOCUMENT"
    UPDATE_DOCUMENT = "UPDATE_DOCUMENT"
    CHANGE_DOCUMENT_CODE = "CHANGE_DOCUMENT_CODE"
    ARCHIVE_DOCUMENT = "ARCHIVE_DOCUMENT"
    RESTORE_DOCUMENT = "RESTORE_DOCUMENT"
    CREATE_DOCUMENT_REVISION = "CREATE_DOCUMENT_REVISION"
    UPDATE_DOCUMENT_REVISION = "UPDATE_DOCUMENT_REVISION"
    SET_CURRENT_REVISION = "SET_CURRENT_REVISION"
    SUPERSEDE_DOCUMENT_REVISION = "SUPERSEDE_DOCUMENT_REVISION"
    IMPORT_DOCUMENT_REGISTER = "IMPORT_DOCUMENT_REGISTER"
    EXPORT_DOCUMENT_REGISTER = "EXPORT_DOCUMENT_REGISTER"
    BULK_ARCHIVE_DOCUMENTS = "BULK_ARCHIVE_DOCUMENTS"
    BULK_RESTORE_DOCUMENTS = "BULK_RESTORE_DOCUMENTS"
    BULK_UPDATE_DOCUMENT_STATUS = "BULK_UPDATE_DOCUMENT_STATUS"

ROLE_PERMISSIONS: Final[Mapping[UserRole, frozenset[Permission]]] = (
    MappingProxyType(
        {
            UserRole.SUPER_ADMIN: frozenset(Permission),
            UserRole.DOCUMENT_CONTROLLER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_CREATE,
                    Permission.DOCUMENTS_UPDATE,
                    Permission.DOCUMENTS_ARCHIVE,
                    Permission.DOCUMENTS_RESTORE,
                    Permission.DOCUMENTS_EXPORT,
                    Permission.DOCUMENTS_IMPORT,
                    Permission.DOCUMENTS_VIEW_ALL_DEPARTMENTS,
                    Permission.DOCUMENTS_MANAGE_REVISIONS,
                    Permission.DOCUMENTS_VALIDATE,
                    Permission.DOCUMENTS_ASSIGN_REVIEWER,
                    Permission.FINDINGS_VIEW,
                    Permission.FINDINGS_UPDATE,
                    Permission.FINDINGS_RESOLVE,
                    Permission.MASTER_DATA_VIEW,
                    Permission.REPORTS_VIEW,
                    Permission.REPORTS_EXPORT,
                }
            ),
            UserRole.REVIEWER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.FINDINGS_VIEW,
                    Permission.FINDINGS_UPDATE,
                    Permission.FINDINGS_RESOLVE,
                    Permission.REPORTS_VIEW,
                }
            ),
            UserRole.DEPARTMENT_USER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_CREATE,
                    Permission.DOCUMENTS_UPDATE,
                    Permission.FINDINGS_VIEW,
                }
            ),
            UserRole.AUDITOR: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_EXPORT,
                    Permission.DOCUMENTS_VIEW_ALL_DEPARTMENTS,
                    Permission.FINDINGS_VIEW,
                    Permission.REPORTS_VIEW,
                    Permission.REPORTS_EXPORT,
                    Permission.AUDIT_LOGS_VIEW,
                }
            ),
            UserRole.VIEWER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                }
            ),
        }
    )
)


def get_permissions(
    role: UserRole | str,
    *,
    is_superuser: bool = False,
) -> list[str]:
    """Return stable API permission strings for one principal."""
    normalized_role = role if isinstance(role, UserRole) else UserRole(role)
    permissions = (
        frozenset(Permission)
        if is_superuser
        else ROLE_PERMISSIONS[normalized_role]
    )
    return sorted(permission.value for permission in permissions)


def has_permission(
    role: UserRole | str,
    permission: Permission | str,
    *,
    is_superuser: bool = False,
) -> bool:
    """Return whether a role grants an atomic capability."""

    value = permission.value if isinstance(permission, Permission) else permission
    return value in get_permissions(role, is_superuser=is_superuser)


role_has_permission = has_permission
