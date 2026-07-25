"""Domain-safe exceptions for API error responses."""

from http import HTTPStatus

from app.schemas.common import ErrorDetail


class ApplicationError(Exception):
    """Expected application error that is safe to expose to API clients."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = HTTPStatus.BAD_REQUEST,
        errors: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors


class AuthenticationError(ApplicationError):
    """Authentication failure with a stable client-safe envelope."""

    def __init__(
        self,
        detail: str = "Authentication credentials are invalid.",
    ) -> None:
        super().__init__(
            "Authentication failed.",
            status_code=HTTPStatus.UNAUTHORIZED,
            errors=[ErrorDetail(field=None, message=detail)],
        )


class AuthorizationError(ApplicationError):
    """Authenticated principal does not have the required access."""

    def __init__(
        self,
        detail: str = "You do not have permission to perform this action.",
    ) -> None:
        super().__init__(
            "Authorization failed.",
            status_code=HTTPStatus.FORBIDDEN,
            errors=[ErrorDetail(field=None, message=detail)],
        )


class AccountLockedError(ApplicationError):
    """Login has been rate-limited for one known account."""

    def __init__(self) -> None:
        super().__init__(
            "Authentication failed.",
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            errors=[
                ErrorDetail(
                    field=None,
                    message=(
                        "Account is temporarily locked due to too many "
                        "login attempts."
                    ),
                )
            ],
        )
