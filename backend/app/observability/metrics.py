"""Small Prometheus-compatible registry with bounded label vocabularies."""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_METRIC_NAME = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
DEFAULT_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    name: str
    help_text: str
    metric_type: str
    label_names: tuple[str, ...]
    allowed_label_values: Mapping[str, frozenset[str]]

    def __post_init__(self) -> None:
        if not _METRIC_NAME.fullmatch(self.name):
            raise ValueError("Metric name is invalid.")
        if self.metric_type not in {"counter", "gauge", "histogram"}:
            raise ValueError("Metric type is unsupported.")
        if any(not _LABEL_NAME.fullmatch(item) for item in self.label_names):
            raise ValueError("Metric label name is invalid.")


class MetricsRegistry:
    """In-process registry suitable for one worker/process scrape."""

    def __init__(self) -> None:
        self._definitions: dict[str, MetricDefinition] = {}
        self._values: dict[str, dict[tuple[str, ...], float]] = defaultdict(dict)
        self._histograms: dict[str, dict[tuple[str, ...], list[float]]] = defaultdict(
            dict
        )
        self._lock = asyncio.Lock()

    def register(self, definition: MetricDefinition) -> None:
        existing = self._definitions.get(definition.name)
        if existing is not None and existing != definition:
            raise ValueError("Metric is already registered differently.")
        self._definitions[definition.name] = definition

    async def increment(
        self,
        name: str,
        *,
        amount: float = 1,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if amount < 0:
            raise ValueError("Counters cannot be decremented.")
        definition, key = self._label_key(name, labels)
        if definition.metric_type != "counter":
            raise ValueError("Metric is not a counter.")
        async with self._lock:
            self._values[name][key] = self._values[name].get(key, 0) + amount

    async def set_gauge(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        definition, key = self._label_key(name, labels)
        if definition.metric_type != "gauge":
            raise ValueError("Metric is not a gauge.")
        async with self._lock:
            self._values[name][key] = value

    async def observe(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if value < 0 or not math.isfinite(value):
            raise ValueError("Histogram observation must be finite and positive.")
        definition, key = self._label_key(name, labels)
        if definition.metric_type != "histogram":
            raise ValueError("Metric is not a histogram.")
        async with self._lock:
            summary = self._histograms[name].setdefault(
                key,
                [0.0] * (len(DEFAULT_BUCKETS) + 2),
            )
            for index, bucket in enumerate(DEFAULT_BUCKETS):
                if value <= bucket:
                    summary[index] += 1
            summary[len(DEFAULT_BUCKETS)] += 1
            summary[len(DEFAULT_BUCKETS) + 1] += value

    async def render(self) -> str:
        async with self._lock:
            lines: list[str] = []
            for name, definition in sorted(self._definitions.items()):
                lines.extend(
                    (
                        f"# HELP {name} {definition.help_text}",
                        f"# TYPE {name} {definition.metric_type}",
                    )
                )
                if definition.metric_type == "histogram":
                    for key, summary in sorted(self._histograms[name].items()):
                        labels = dict(zip(definition.label_names, key, strict=True))
                        for index, bucket in enumerate(DEFAULT_BUCKETS):
                            bucket_labels = {**labels, "le": str(bucket)}
                            lines.append(
                                f"{name}_bucket{self._format_labels(bucket_labels)} "
                                f"{summary[index]:g}"
                            )
                        infinity_labels = {**labels, "le": "+Inf"}
                        lines.append(
                            f"{name}_bucket{self._format_labels(infinity_labels)} "
                            f"{summary[len(DEFAULT_BUCKETS)]:g}"
                        )
                        lines.append(
                            f"{name}_count{self._format_labels(labels)} "
                            f"{summary[len(DEFAULT_BUCKETS)]:g}"
                        )
                        lines.append(
                            f"{name}_sum{self._format_labels(labels)} "
                            f"{summary[len(DEFAULT_BUCKETS) + 1]:g}"
                        )
                else:
                    for key, value in sorted(self._values[name].items()):
                        labels = dict(zip(definition.label_names, key, strict=True))
                        lines.append(f"{name}{self._format_labels(labels)} {value:g}")
            return "\n".join(lines) + "\n"

    def _label_key(
        self,
        name: str,
        labels: Mapping[str, str] | None,
    ) -> tuple[MetricDefinition, tuple[str, ...]]:
        definition = self._definitions.get(name)
        if definition is None:
            raise KeyError(f"Metric '{name}' is not registered.")
        provided = dict(labels or {})
        if set(provided) != set(definition.label_names):
            raise ValueError("Metric labels do not match its definition.")
        for label_name, value in provided.items():
            allowed = definition.allowed_label_values.get(label_name)
            if allowed is not None and value not in allowed:
                raise ValueError("Metric label value is outside its bounded set.")
            if len(value) > 100:
                raise ValueError("Metric label value is too long.")
        return definition, tuple(provided[item] for item in definition.label_names)

    @staticmethod
    def _format_labels(labels: Mapping[str, str]) -> str:
        if not labels:
            return ""
        content = ",".join(
            f'{key}="{_escape_label(value)}"' for key, value in sorted(labels.items())
        )
        return "{" + content + "}"


def create_default_registry() -> MetricsRegistry:
    registry = MetricsRegistry()
    http_methods = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
    worker_types = frozenset(
        {
            "extraction",
            "ocr",
            "language",
            "compliance",
            "similarity",
            "glossary",
            "revision",
            "reporting",
            "sharepoint",
            "notifications",
            "maintenance",
        }
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_http_requests_total",
            help_text="HTTP requests handled by the API.",
            metric_type="counter",
            label_names=("method", "status_class"),
            allowed_label_values={
                "method": http_methods,
                "status_class": frozenset({"2xx", "3xx", "4xx", "5xx"}),
            },
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_http_request_duration_seconds",
            help_text="HTTP request duration in seconds.",
            metric_type="histogram",
            label_names=("method",),
            allowed_label_values={"method": http_methods},
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_http_errors_total",
            help_text="HTTP client and server errors.",
            metric_type="counter",
            label_names=("method", "status_class"),
            allowed_label_values={
                "method": http_methods,
                "status_class": frozenset({"4xx", "5xx"}),
            },
        )
    )
    for name, help_text in (
        (
            "document_compliance_db_connections_active",
            "Active database connections.",
        ),
        (
            "document_compliance_redis_up",
            "Redis connectivity state (one for available).",
        ),
    ):
        registry.register(
            MetricDefinition(
                name=name,
                help_text=help_text,
                metric_type="gauge",
                label_names=(),
                allowed_label_values={},
            )
        )
    registry.register(
        MetricDefinition(
            name="document_compliance_celery_queue_depth",
            help_text="Approximate pending Celery messages by bounded queue.",
            metric_type="gauge",
            label_names=("queue",),
            allowed_label_values={
                "queue": frozenset(
                    {
                        "extraction",
                        "ocr",
                        "language",
                        "compliance",
                        "similarity",
                        "glossary",
                        "revision",
                        "reporting",
                        "sharepoint",
                        "notifications",
                        "maintenance",
                    }
                )
            },
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_task_duration_seconds",
            help_text="Background task execution duration.",
            metric_type="histogram",
            label_names=("task_type",),
            allowed_label_values={"task_type": worker_types},
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_task_failures_total",
            help_text="Background task failures.",
            metric_type="counter",
            label_names=("task_type",),
            allowed_label_values={"task_type": worker_types},
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_transfer_bytes_total",
            help_text="Upload and download bytes.",
            metric_type="counter",
            label_names=("direction",),
            allowed_label_values={"direction": frozenset({"upload", "download"})},
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_pipeline_duration_seconds",
            help_text="Document processing pipeline duration.",
            metric_type="histogram",
            label_names=("stage",),
            allowed_label_values={
                "stage": frozenset(
                    {
                        "extraction",
                        "ocr",
                        "compliance",
                        "similarity",
                        "report_generation",
                    }
                )
            },
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_sharepoint_requests_total",
            help_text="Microsoft Graph and SharePoint request outcomes.",
            metric_type="counter",
            label_names=("outcome",),
            allowed_label_values={
                "outcome": frozenset({"success", "error", "throttled", "conflict"})
            },
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_graph_throttling_total",
            help_text="Microsoft Graph throttling responses.",
            metric_type="counter",
            label_names=(),
            allowed_label_values={},
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_sharepoint_sync_items_total",
            help_text="SharePoint sync item outcomes.",
            metric_type="counter",
            label_names=("outcome",),
            allowed_label_values={
                "outcome": frozenset({"created", "updated", "skipped", "failed"})
            },
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_sharepoint_conflicts_total",
            help_text="SharePoint conflicts observed.",
            metric_type="counter",
            label_names=("action",),
            allowed_label_values={
                "action": frozenset({"created", "resolved", "ignored"})
            },
        )
    )
    registry.register(
        MetricDefinition(
            name="document_compliance_notification_deliveries_total",
            help_text="Notification delivery outcomes.",
            metric_type="counter",
            label_names=("channel", "outcome"),
            allowed_label_values={
                "channel": frozenset({"IN_APP", "EMAIL_GRAPH", "TEAMS", "TELEGRAM"}),
                "outcome": frozenset({"success", "failure"}),
            },
        )
    )
    return registry


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, registry: MetricsRegistry) -> None:
        super().__init__(app)
        self.registry = registry

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            method = request.method.upper()
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
                method = "OTHER"
            if method != "OTHER":
                await self.registry.increment(
                    "document_compliance_http_requests_total",
                    labels={
                        "method": method,
                        "status_class": f"{status_code // 100}xx",
                    },
                )
                await self.registry.observe(
                    "document_compliance_http_request_duration_seconds",
                    time.perf_counter() - started,
                    labels={"method": method},
                )
                if status_code >= 400:
                    await self.registry.increment(
                        "document_compliance_http_errors_total",
                        labels={
                            "method": method,
                            "status_class": f"{status_code // 100}xx",
                        },
                    )
