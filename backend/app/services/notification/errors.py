"""Stable client-safe notification errors."""

from http import HTTPStatus

from app.core.exceptions import ApplicationError
from app.schemas.common import ErrorDetail


def notification_error(
    message: str,
    *,
    code: str,
    status_code: int = HTTPStatus.BAD_REQUEST,
    title: str = "Notification request failed.",
) -> ApplicationError:
    return ApplicationError(
        title,
        status_code=status_code,
        errors=[ErrorDetail(field=None, message=message, code=code)],
    )
