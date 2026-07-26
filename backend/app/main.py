"""FastAPI application factory and ASGI entry point."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.endpoints.system_health import (
    get_additional_health_probes,
)
from app.api.v1.endpoints.admin_notifications import (
    get_notification_retry_publisher,
)
from app.api.v1.endpoints.dead_letter import (
    get_dead_letter_retry_publisher,
)
from app.api.v1.endpoints.system_health import (
    public_router as public_health_router,
)
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.rate_limit_middleware import (
    RateLimitMiddleware,
    default_route_rate_limits,
)
from app.core.request_id import RequestIdMiddleware
from app.core.request_size_limit import RequestSizeLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.structured_logging import configure_application_logging
from app.database.session import dispose_engine, engine
from app.observability.metrics import (
    MetricsMiddleware,
    create_default_registry,
)
from app.observability.metrics_endpoint import create_metrics_router
from app.observability.tracing import (
    TracingConfiguration,
    configure_opentelemetry,
)
from app.services.security.rate_limiter import RedisRateLimiter
from app.services.storage.storage_factory import close_default_storage
from app.services.system_health_service import DependencyProbe


def _create_redis_client(settings: Settings) -> Redis:
    password = (
        settings.redis_password.get_secret_value()
        if settings.redis_password is not None
        else None
    )
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=password,
        ssl=settings.redis_ssl,
        socket_timeout=settings.redis_socket_timeout_seconds,
        socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
        health_check_interval=settings.redis_health_check_interval_seconds,
        max_connections=settings.redis_max_connections,
        decode_responses=True,
    )


def _health_probes(
    settings: Settings,
    redis_client: Redis,
) -> tuple[DependencyProbe, ...]:
    async def redis_check() -> dict[str, object]:
        return {"connected": bool(await redis_client.ping())}

    async def storage_check() -> dict[str, object]:
        root = settings.storage_root.resolve()

        def inspect() -> dict[str, object]:
            root.mkdir(parents=True, exist_ok=True)
            return {
                "provider": settings.storage_provider,
                "available": root.is_dir() and os.access(root, os.R_OK | os.W_OK),
            }

        result = await asyncio.to_thread(inspect)
        if not result["available"]:
            raise OSError("Storage root is unavailable.")
        return result

    async def configuration_check() -> dict[str, object]:
        return {
            "environment": settings.environment,
            "graphEnabled": settings.microsoft_graph_enabled,
            "sharePointSyncEnabled": settings.sharepoint_sync_enabled,
        }

    async def graph_configuration_check() -> dict[str, object]:
        if not settings.microsoft_tenant_id or not settings.microsoft_client_id:
            raise ValueError("Microsoft Graph configuration is incomplete.")
        return {
            "configured": True,
            "authMode": settings.microsoft_graph_auth_mode.upper(),
        }

    async def malware_scanner_check() -> dict[str, object]:
        reader, writer = await asyncio.open_connection(
            settings.clamav_host,
            settings.clamav_port,
        )
        del reader
        writer.close()
        await writer.wait_closed()
        return {"scanner": settings.malware_scanner, "connected": True}

    return (
        DependencyProbe(name="redis", check=redis_check),
        DependencyProbe(name="storage", check=storage_check),
        DependencyProbe(name="configuration", check=configuration_check),
        DependencyProbe(
            name="microsoft_graph",
            check=graph_configuration_check,
            mandatory=settings.microsoft_graph_enabled,
            enabled=settings.microsoft_graph_enabled,
        ),
        DependencyProbe(
            name="malware_scanner",
            check=malware_scanner_check,
            mandatory=settings.malware_scanning_enabled,
            enabled=settings.malware_scanning_enabled,
        ),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the API application."""
    app_settings = settings or get_settings()
    configure_application_logging(
        level=app_settings.log_level,
        json_enabled=app_settings.log_format == "json",
    )
    redis_client = _create_redis_client(app_settings)
    metrics_registry = create_default_registry()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            graph_client = getattr(application.state, "graph_client", None)
            if graph_client is not None and hasattr(graph_client, "close"):
                await graph_client.close()
            await close_default_storage()
            await cast(Any, redis_client).aclose()
            await dispose_engine()

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        docs_url=None if app_settings.environment == "production" else "/docs",
        redoc_url=None if app_settings.environment == "production" else "/redoc",
        openapi_url=(
            None if app_settings.environment == "production" else "/openapi.json"
        ),
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.redis = redis_client
    application.state.metrics_registry = metrics_registry

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
        allow_credentials=(
            app_settings.cors_allow_credentials and "*" not in cors_origins
        ),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "If-Match",
            "If-None-Match",
            "X-Request-ID",
        ],
        expose_headers=[
            "Content-Disposition",
            "ETag",
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-Request-ID",
        ],
    )
    application.add_middleware(
        RateLimitMiddleware,
        limiter=RedisRateLimiter(
            redis_client,
            namespace=app_settings.redis_key_prefix,
            enabled=(
                app_settings.rate_limit_enabled and app_settings.environment != "test"
            ),
            fail_open=False,
        ),
        route_limits=default_route_rate_limits(
            api_prefix=app_settings.api_v1_prefix,
            limits={
                "login": app_settings.rate_limit_login_per_minute,
                "upload": app_settings.rate_limit_upload_per_minute,
                "reports": app_settings.rate_limit_reports_per_hour,
                "sync": app_settings.rate_limit_sync_per_hour,
                "connection_test": (app_settings.rate_limit_connection_test_per_minute),
            },
        ),
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=app_settings.trusted_host_list,
    )
    if app_settings.metrics_enabled:
        application.add_middleware(
            MetricsMiddleware,
            registry=metrics_registry,
        )
    application.add_middleware(
        SecurityHeadersMiddleware,
        production=app_settings.environment == "production",
    )
    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    application.include_router(public_health_router)
    if app_settings.metrics_enabled:
        metrics_access_token = (
            app_settings.metrics_auth_token.get_secret_value()
            if app_settings.metrics_auth_token is not None
            else None
        )
        application.include_router(
            create_metrics_router(
                metrics_registry,
                access_token=metrics_access_token,
            )
        )
    application.dependency_overrides[get_additional_health_probes] = lambda: (
        _health_probes(app_settings, redis_client)
    )
    from app.workers.notification_tasks import (
        get_runtime_notification_retry_publisher,
    )
    from app.workers.maintenance_tasks import (
        get_runtime_dead_letter_retry_publisher,
    )

    application.dependency_overrides[get_notification_retry_publisher] = (
        get_runtime_notification_retry_publisher
    )
    application.dependency_overrides[get_dead_letter_retry_publisher] = (
        get_runtime_dead_letter_retry_publisher
    )
    configure_opentelemetry(
        TracingConfiguration(
            enabled=app_settings.otel_enabled,
            service_name=app_settings.otel_service_name,
            exporter_otlp_endpoint=app_settings.otel_exporter_otlp_endpoint,
            sample_ratio=app_settings.otel_trace_sample_ratio,
        ),
        app=application,
        sqlalchemy_engine=engine.sync_engine,
        redis_client=redis_client,
    )
    return application


app = create_app()
