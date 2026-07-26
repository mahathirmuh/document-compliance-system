# Monitoring and alerting

Prometheus-compatible metrics expose bounded labels only. Never label metrics
with document codes, filenames, email addresses, remote paths, or user IDs.

Recommended alerts:

- API readiness unavailable for 5 minutes
- PostgreSQL or Redis unavailable
- worker heartbeat older than two expected intervals
- queue depth or oldest-task age above operational threshold
- Graph 429/503 rate sustained above baseline
- SharePoint connection degraded or authentication failed
- webhook subscription expiring/renewal failed
- sync failure or dead-letter rate increasing
- unresolved conflict backlog above owner-approved threshold
- notification remote-channel failure rate increasing
- disk capacity below 15%
- malware scanner unavailable while fail-closed is enabled
- backup missed or latest restore test outside policy

Dashboards should cover HTTP latency/errors, DB pool utilization, Redis health,
Celery depth/duration/failures, upload/download bytes, document pipeline
duration, Graph requests/throttling, sync items/conflicts, notification
delivery, and reports.

Tracing is optional and controlled by `OTEL_ENABLED`. Spans may contain request,
job, and safe entity IDs but never full document text, secrets, tokens, delta
links, webhook payloads, or notification bodies.
