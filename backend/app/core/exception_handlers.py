"""Global exception handlers with a consistent, production-safe envelope."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ApplicationError
from app.schemas.common import ApiResponse, ErrorDetail

logger = logging.getLogger(__name__)


def _error_response(
    *,
    status_code: int,
    message: str,
    errors: list[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ApiResponse[Any](
        success=False,
        message=message,
        data=None,
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


async def application_error_handler(
    _: Request, exc: ApplicationError
) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        message=exc.message,
        errors=exc.errors,
    )


async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        ErrorDetail(
            field=".".join(str(segment) for segment in error["loc"]),
            message=error["msg"],
        )
        for error in exc.errors()
    ]
    return _error_response(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        message="Request validation failed.",
        errors=errors,
    )


async def http_error_handler(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _error_response(status_code=exc.status_code, message=message)


async def unexpected_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled exception while processing %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _error_response(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register handlers in one place for every API endpoint."""
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
