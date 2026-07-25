"""ASGI request-body limits applied before multipart form parsing."""

from __future__ import annotations

from http import HTTPStatus

from fastapi.responses import JSONResponse
from starlette.formparsers import MultiPartException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas.common import ApiResponse, ErrorDetail


class _RequestBodyTooLarge(MultiPartException):
    """Internal control flow raised by the bounded ASGI receive wrapper."""


class RequestSizeLimitMiddleware:
    """Bound declared and chunked bodies before Starlette spools uploads."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        api_prefix: str,
        default_max_body_size: int,
        single_upload_max_body_size: int,
        batch_upload_max_body_size: int,
    ) -> None:
        limits = (
            default_max_body_size,
            single_upload_max_body_size,
            batch_upload_max_body_size,
        )
        if any(limit <= 0 for limit in limits):
            raise ValueError("Request body limits must be positive.")
        self.app = app
        self.api_prefix = api_prefix.rstrip("/")
        self.default_max_body_size = default_max_body_size
        self.single_upload_max_body_size = single_upload_max_body_size
        self.batch_upload_max_body_size = batch_upload_max_body_size

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        maximum = self._maximum_for_path(scope.get("path", ""))
        content_length = self._content_length(scope)
        if content_length is not None and content_length > maximum:
            await self._reject(scope, receive, send)
            return

        received = 0
        response_started = False
        too_large = False

        async def bounded_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > maximum:
                    too_large = True
                    raise _RequestBodyTooLarge(
                        "Request body exceeds the configured size limit."
                    )
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if too_large:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(scope, receive, send)
            return
        if too_large:
            if response_started:
                raise _RequestBodyTooLarge(
                    "Request body exceeds the configured size limit."
                )
            await self._reject(scope, receive, send)

    def _maximum_for_path(self, path: str) -> int:
        normalized = path.rstrip("/")
        batch_path = (
            f"{self.api_prefix}/document-files/batch-upload"
        )
        single_path = f"{self.api_prefix}/document-files/upload"
        if normalized == batch_path:
            return self.batch_upload_max_body_size
        if normalized == single_path or (
            normalized.startswith(
                f"{self.api_prefix}/document-files/"
            )
            and normalized.endswith("/replace")
        ):
            return self.single_upload_max_body_size
        return self.default_max_body_size

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        values = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if not values:
            return None
        try:
            lengths = [int(value) for value in values]
        except ValueError:
            return None
        nonnegative = [length for length in lengths if length >= 0]
        return max(nonnegative) if nonnegative else None

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        payload = ApiResponse[None](
            success=False,
            message="Request body exceeds the configured size limit.",
            data=None,
            errors=[
                ErrorDetail(
                    field="body",
                    message="Upload a smaller request.",
                )
            ],
        )
        response = JSONResponse(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            content=payload.model_dump(mode="json"),
        )
        await response(scope, receive, send)
