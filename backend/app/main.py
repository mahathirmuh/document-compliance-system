"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.request_size_limit import RequestSizeLimitMiddleware
from app.database.session import dispose_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the API application."""
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await dispose_engine()

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        RequestSizeLimitMiddleware,
        api_prefix=app_settings.api_v1_prefix,
        default_max_body_size=app_settings.request_body_max_size_bytes,
        single_upload_max_body_size=(
            app_settings.document_single_upload_request_limit_bytes
        ),
        batch_upload_max_body_size=(
            app_settings.document_batch_upload_request_limit_bytes
        ),
    )
    cors_origins = app_settings.cors_origin_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return application


app = create_app()
