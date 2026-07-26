"""Optional OpenTelemetry wiring without importing SDKs when disabled."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.log_redaction import redact_url


@dataclass(frozen=True, slots=True)
class TracingConfiguration:
    enabled: bool = False
    service_name: str = "document-compliance-api"
    exporter_otlp_endpoint: str | None = None
    sample_ratio: float = 0.1

    def __post_init__(self) -> None:
        if not 0 <= self.sample_ratio <= 1:
            raise ValueError("OTEL sample ratio must be between zero and one.")
        if self.enabled and not self.exporter_otlp_endpoint:
            raise ValueError("OTEL exporter endpoint is required when enabled.")


def configure_opentelemetry(
    configuration: TracingConfiguration,
    *,
    app: Any,
    sqlalchemy_engine: Any | None = None,
    redis_client: Any | None = None,
    celery_app: Any | None = None,
) -> bool:
    """Wire official instrumentors if optional packages are installed."""

    if not configuration.enabled:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import (
            FastAPIInstrumentor,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError as exc:
        raise RuntimeError(
            "OpenTelemetry packages are required when OTEL is enabled."
        ) from exc
    provider = TracerProvider(
        resource=Resource.create({"service.name": configuration.service_name}),
        sampler=TraceIdRatioBased(configuration.sample_ratio),
    )
    exporter = OTLPSpanExporter(endpoint=configuration.exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="/health/live,/health/ready,/metrics",
    )
    try:
        from opentelemetry.instrumentation.httpx import (
            HTTPXClientInstrumentor,
        )

        HTTPXClientInstrumentor().instrument(
            tracer_provider=provider,
            request_hook=_redact_httpx_request,
        )
    except ImportError:
        pass
    _instrument_optional(
        provider,
        sqlalchemy_engine=sqlalchemy_engine,
        redis_client=redis_client,
        celery_app=celery_app,
    )
    return True


def _redact_httpx_request(
    span: Any,
    request: Any,
) -> None:
    """Replace any Graph delta/token query before span export."""

    if span is None or not getattr(span, "is_recording", lambda: False)():
        return
    url = getattr(request, "url", None)
    if url is None:
        return
    safe_url = redact_url(str(url))
    span.set_attribute("url.full", safe_url)
    span.set_attribute("http.url", safe_url)


def _instrument_optional(
    provider: Any,
    *,
    sqlalchemy_engine: Any | None,
    redis_client: Any | None,
    celery_app: Any | None,
) -> None:
    if sqlalchemy_engine is not None:
        try:
            from opentelemetry.instrumentation.sqlalchemy import (
                SQLAlchemyInstrumentor,
            )

            SQLAlchemyInstrumentor().instrument(
                engine=sqlalchemy_engine,
                tracer_provider=provider,
            )
        except ImportError:
            pass
    if redis_client is not None:
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor

            RedisInstrumentor().instrument(tracer_provider=provider)
        except ImportError:
            pass
    if celery_app is not None:
        try:
            from opentelemetry.instrumentation.celery import CeleryInstrumentor

            CeleryInstrumentor().instrument(tracer_provider=provider)
        except ImportError:
            pass
