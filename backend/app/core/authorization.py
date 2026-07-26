"""Canonical roles, permissions, and auditable action names."""

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import Final


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
    DOCUMENTS_UPLOAD = "documents:upload"
    DOCUMENTS_DOWNLOAD = "documents:download"
    DOCUMENTS_REPLACE_FILE = "documents:replace_file"
    DOCUMENTS_DELETE_FILE = "documents:delete_file"
    DOCUMENTS_BATCH_UPLOAD = "documents:batch_upload"
    DOCUMENTS_VIEW_FILE_HISTORY = "documents:view_file_history"
    DOCUMENTS_EXTRACT = "documents:extract"
    DOCUMENTS_REEXTRACT = "documents:reextract"
    DOCUMENTS_VIEW_EXTRACTED_CONTENT = (
        "documents:view_extracted_content"
    )
    DOCUMENTS_EXPORT_EXTRACTED_CONTENT = (
        "documents:export_extracted_content"
    )
    DOCUMENTS_VIEW_EXTRACTION_HISTORY = (
        "documents:view_extraction_history"
    )
    DOCUMENTS_CANCEL_EXTRACTION = "documents:cancel_extraction"
    DOCUMENTS_OCR = "documents:ocr"
    DOCUMENTS_REOCR = "documents:reocr"
    DOCUMENTS_VIEW_OCR_RESULTS = "documents:view_ocr_results"
    DOCUMENTS_VIEW_OCR_HISTORY = "documents:view_ocr_history"
    DOCUMENTS_CANCEL_OCR = "documents:cancel_ocr"
    DOCUMENTS_DETECT_LANGUAGE = "documents:detect_language"
    DOCUMENTS_REDETECT_LANGUAGE = "documents:redetect_language"
    DOCUMENTS_VIEW_LANGUAGE_RESULTS = "documents:view_language_results"
    DOCUMENTS_EXPORT_LANGUAGE_RESULTS = (
        "documents:export_language_results"
    )
    DOCUMENTS_REVIEW_LANGUAGE_RESULT = (
        "documents:review_language_result"
    )
    DOCUMENTS_DELETE = "documents:delete"
    DOCUMENTS_VALIDATE = "documents:validate"
    DOCUMENTS_ASSIGN_REVIEWER = "documents:assign_reviewer"
    COMPLIANCE_VIEW = "compliance:view"
    COMPLIANCE_VALIDATE = "compliance:validate"
    COMPLIANCE_REVALIDATE = "compliance:revalidate"
    COMPLIANCE_VIEW_ALL_DEPARTMENTS = (
        "compliance:view_all_departments"
    )
    COMPLIANCE_EXPORT = "compliance:export"
    COMPLIANCE_CONFIGURE_RULES = "compliance:configure_rules"
    FINDINGS_VIEW = "findings:view"
    FINDINGS_CREATE_MANUAL = "findings:create_manual"
    FINDINGS_UPDATE = "findings:update"
    FINDINGS_REVIEW = "findings:review"
    FINDINGS_RESOLVE = "findings:resolve"
    FINDINGS_REOPEN = "findings:reopen"
    FINDINGS_FALSE_POSITIVE = "findings:false_positive"
    FINDINGS_EXPORT = "findings:export"
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
    UPLOAD_FILE_PREVIEW = "UPLOAD_FILE_PREVIEW"
    CONFIRM_FILE_UPLOAD = "CONFIRM_FILE_UPLOAD"
    CANCEL_FILE_UPLOAD = "CANCEL_FILE_UPLOAD"
    BATCH_UPLOAD_PREVIEW = "BATCH_UPLOAD_PREVIEW"
    CONFIRM_BATCH_UPLOAD = "CONFIRM_BATCH_UPLOAD"
    ATTACH_FILE_TO_REVISION = "ATTACH_FILE_TO_REVISION"
    CREATE_DOCUMENT_FROM_UPLOAD = "CREATE_DOCUMENT_FROM_UPLOAD"
    CREATE_REVISION_FROM_UPLOAD = "CREATE_REVISION_FROM_UPLOAD"
    REPLACE_DOCUMENT_FILE = "REPLACE_DOCUMENT_FILE"
    DELETE_DOCUMENT_FILE = "DELETE_DOCUMENT_FILE"
    RESTORE_DOCUMENT_FILE = "RESTORE_DOCUMENT_FILE"
    DOWNLOAD_DOCUMENT_FILE = "DOWNLOAD_DOCUMENT_FILE"
    QUARANTINE_DOCUMENT_FILE = "QUARANTINE_DOCUMENT_FILE"
    DUPLICATE_FILE_DETECTED = "DUPLICATE_FILE_DETECTED"
    CLEANUP_EXPIRED_UPLOAD_SESSION = "CLEANUP_EXPIRED_UPLOAD_SESSION"
    QUEUE_DOCUMENT_EXTRACTION = "QUEUE_DOCUMENT_EXTRACTION"
    START_DOCUMENT_EXTRACTION = "START_DOCUMENT_EXTRACTION"
    COMPLETE_DOCUMENT_EXTRACTION = "COMPLETE_DOCUMENT_EXTRACTION"
    PARTIAL_DOCUMENT_EXTRACTION = "PARTIAL_DOCUMENT_EXTRACTION"
    DOCUMENT_REQUIRES_OCR = "DOCUMENT_REQUIRES_OCR"
    FAIL_DOCUMENT_EXTRACTION = "FAIL_DOCUMENT_EXTRACTION"
    CANCEL_DOCUMENT_EXTRACTION = "CANCEL_DOCUMENT_EXTRACTION"
    REEXTRACT_DOCUMENT = "REEXTRACT_DOCUMENT"
    VIEW_EXTRACTED_CONTENT = "VIEW_EXTRACTED_CONTENT"
    SEARCH_EXTRACTED_CONTENT = "SEARCH_EXTRACTED_CONTENT"
    EXPORT_EXTRACTED_CONTENT = "EXPORT_EXTRACTED_CONTENT"
    QUEUE_OCR = "QUEUE_OCR"
    START_OCR = "START_OCR"
    COMPLETE_OCR = "COMPLETE_OCR"
    PARTIAL_OCR = "PARTIAL_OCR"
    FAIL_OCR = "FAIL_OCR"
    CANCEL_OCR = "CANCEL_OCR"
    REOCR_DOCUMENT = "REOCR_DOCUMENT"
    EXPORT_OCR_RESULT = "EXPORT_OCR_RESULT"
    QUEUE_LANGUAGE_DETECTION = "QUEUE_LANGUAGE_DETECTION"
    START_LANGUAGE_DETECTION = "START_LANGUAGE_DETECTION"
    COMPLETE_LANGUAGE_DETECTION = "COMPLETE_LANGUAGE_DETECTION"
    FAIL_LANGUAGE_DETECTION = "FAIL_LANGUAGE_DETECTION"
    CANCEL_LANGUAGE_DETECTION = "CANCEL_LANGUAGE_DETECTION"
    REDETECT_LANGUAGE = "REDETECT_LANGUAGE"
    EXPORT_LANGUAGE_RESULT = "EXPORT_LANGUAGE_RESULT"
    REVIEW_LANGUAGE_RESULT = "REVIEW_LANGUAGE_RESULT"
    QUEUE_COMPLIANCE_VALIDATION = "QUEUE_COMPLIANCE_VALIDATION"
    START_COMPLIANCE_VALIDATION = "START_COMPLIANCE_VALIDATION"
    COMPLETE_COMPLIANCE_VALIDATION = "COMPLETE_COMPLIANCE_VALIDATION"
    PARTIAL_COMPLIANCE_VALIDATION = "PARTIAL_COMPLIANCE_VALIDATION"
    FAIL_COMPLIANCE_VALIDATION = "FAIL_COMPLIANCE_VALIDATION"
    CANCEL_COMPLIANCE_VALIDATION = "CANCEL_COMPLIANCE_VALIDATION"
    REVALIDATE_COMPLIANCE = "REVALIDATE_COMPLIANCE"
    EXPORT_COMPLIANCE_RESULT = "EXPORT_COMPLIANCE_RESULT"
    CREATE_FINDING = "CREATE_FINDING"
    CREATE_MANUAL_FINDING = "CREATE_MANUAL_FINDING"
    UPDATE_FINDING = "UPDATE_FINDING"
    REVIEW_FINDING = "REVIEW_FINDING"
    RESOLVE_FINDING = "RESOLVE_FINDING"
    REOPEN_FINDING = "REOPEN_FINDING"
    MARK_FINDING_FALSE_POSITIVE = "MARK_FINDING_FALSE_POSITIVE"
    ACCEPT_FINDING_RISK = "ACCEPT_FINDING_RISK"
    ASSIGN_FINDING = "ASSIGN_FINDING"
    EXPORT_FINDINGS = "EXPORT_FINDINGS"
    CREATE_SECTION_DEFINITION = "CREATE_SECTION_DEFINITION"
    UPDATE_SECTION_DEFINITION = "UPDATE_SECTION_DEFINITION"
    CREATE_SECTION_ALIAS = "CREATE_SECTION_ALIAS"
    UPDATE_SECTION_ALIAS = "UPDATE_SECTION_ALIAS"
    IMPORT_SECTION_ALIASES = "IMPORT_SECTION_ALIASES"
    EXPORT_SECTION_ALIASES = "EXPORT_SECTION_ALIASES"

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
                    Permission.DOCUMENTS_UPLOAD,
                    Permission.DOCUMENTS_DOWNLOAD,
                    Permission.DOCUMENTS_REPLACE_FILE,
                    Permission.DOCUMENTS_DELETE_FILE,
                    Permission.DOCUMENTS_BATCH_UPLOAD,
                    Permission.DOCUMENTS_VIEW_FILE_HISTORY,
                    Permission.DOCUMENTS_EXTRACT,
                    Permission.DOCUMENTS_REEXTRACT,
                    Permission.DOCUMENTS_VIEW_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_EXPORT_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY,
                    Permission.DOCUMENTS_CANCEL_EXTRACTION,
                    Permission.DOCUMENTS_OCR,
                    Permission.DOCUMENTS_REOCR,
                    Permission.DOCUMENTS_VIEW_OCR_RESULTS,
                    Permission.DOCUMENTS_VIEW_OCR_HISTORY,
                    Permission.DOCUMENTS_CANCEL_OCR,
                    Permission.DOCUMENTS_DETECT_LANGUAGE,
                    Permission.DOCUMENTS_REDETECT_LANGUAGE,
                    Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                    Permission.DOCUMENTS_EXPORT_LANGUAGE_RESULTS,
                    Permission.DOCUMENTS_REVIEW_LANGUAGE_RESULT,
                    Permission.DOCUMENTS_VALIDATE,
                    Permission.DOCUMENTS_ASSIGN_REVIEWER,
                    Permission.COMPLIANCE_VIEW,
                    Permission.COMPLIANCE_VALIDATE,
                    Permission.COMPLIANCE_REVALIDATE,
                    Permission.COMPLIANCE_VIEW_ALL_DEPARTMENTS,
                    Permission.COMPLIANCE_EXPORT,
                    Permission.FINDINGS_VIEW,
                    Permission.FINDINGS_CREATE_MANUAL,
                    Permission.FINDINGS_UPDATE,
                    Permission.FINDINGS_REVIEW,
                    Permission.FINDINGS_RESOLVE,
                    Permission.FINDINGS_REOPEN,
                    Permission.FINDINGS_FALSE_POSITIVE,
                    Permission.FINDINGS_EXPORT,
                    Permission.MASTER_DATA_VIEW,
                    Permission.REPORTS_VIEW,
                    Permission.REPORTS_EXPORT,
                }
            ),
            UserRole.REVIEWER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_DOWNLOAD,
                    Permission.DOCUMENTS_VIEW_FILE_HISTORY,
                    Permission.DOCUMENTS_VIEW_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY,
                    Permission.DOCUMENTS_VIEW_OCR_RESULTS,
                    Permission.DOCUMENTS_VIEW_OCR_HISTORY,
                    Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                    Permission.DOCUMENTS_REVIEW_LANGUAGE_RESULT,
                    Permission.COMPLIANCE_VIEW,
                    Permission.FINDINGS_VIEW,
                    Permission.FINDINGS_REVIEW,
                    Permission.FINDINGS_RESOLVE,
                    Permission.FINDINGS_REOPEN,
                    Permission.FINDINGS_FALSE_POSITIVE,
                    Permission.REPORTS_VIEW,
                }
            ),
            UserRole.DEPARTMENT_USER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_CREATE,
                    Permission.DOCUMENTS_UPDATE,
                    Permission.DOCUMENTS_UPLOAD,
                    Permission.DOCUMENTS_DOWNLOAD,
                    Permission.DOCUMENTS_VIEW_FILE_HISTORY,
                    Permission.DOCUMENTS_EXTRACT,
                    Permission.DOCUMENTS_VIEW_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY,
                    Permission.DOCUMENTS_OCR,
                    Permission.DOCUMENTS_VIEW_OCR_RESULTS,
                    Permission.DOCUMENTS_VIEW_OCR_HISTORY,
                    Permission.DOCUMENTS_DETECT_LANGUAGE,
                    Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                    Permission.COMPLIANCE_VIEW,
                    Permission.COMPLIANCE_VALIDATE,
                    Permission.FINDINGS_VIEW,
                    Permission.FINDINGS_UPDATE,
                }
            ),
            UserRole.AUDITOR: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_EXPORT,
                    Permission.DOCUMENTS_VIEW_ALL_DEPARTMENTS,
                    Permission.DOCUMENTS_DOWNLOAD,
                    Permission.DOCUMENTS_VIEW_FILE_HISTORY,
                    Permission.DOCUMENTS_VIEW_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_EXPORT_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_VIEW_EXTRACTION_HISTORY,
                    Permission.DOCUMENTS_VIEW_OCR_RESULTS,
                    Permission.DOCUMENTS_VIEW_OCR_HISTORY,
                    Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                    Permission.DOCUMENTS_EXPORT_LANGUAGE_RESULTS,
                    Permission.COMPLIANCE_VIEW,
                    Permission.COMPLIANCE_VIEW_ALL_DEPARTMENTS,
                    Permission.COMPLIANCE_EXPORT,
                    Permission.FINDINGS_VIEW,
                    Permission.FINDINGS_EXPORT,
                    Permission.REPORTS_VIEW,
                    Permission.REPORTS_EXPORT,
                    Permission.AUDIT_LOGS_VIEW,
                }
            ),
            UserRole.VIEWER: frozenset(
                {
                    Permission.DASHBOARD_VIEW,
                    Permission.DOCUMENTS_VIEW,
                    Permission.DOCUMENTS_DOWNLOAD,
                    Permission.DOCUMENTS_VIEW_EXTRACTED_CONTENT,
                    Permission.DOCUMENTS_VIEW_OCR_RESULTS,
                    Permission.DOCUMENTS_VIEW_LANGUAGE_RESULTS,
                    Permission.COMPLIANCE_VIEW,
                    Permission.FINDINGS_VIEW,
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
