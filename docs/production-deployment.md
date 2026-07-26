# Production deployment

Production uses the multi-stage backend/frontend images, Gunicorn with Uvicorn
workers, dedicated Celery queues, Celery Beat, PostgreSQL, password-protected
Redis, and an HTTPS Nginx edge.

## Prerequisites

- Docker Engine with Compose v2
- CA-issued TLS certificate
- protected `.env.production`
- persistent PostgreSQL, Redis, and document-storage volumes
- local multilingual models mounted read-only
- Entra certificate/secret supplied outside the image

Production validation also requires a non-empty Redis password, an
environment-specific Redis key namespace, authenticated Celery broker/result
URLs (URL-encode the same password), and a base64-encoded AES key of 16, 24,
or preferably 32 random bytes. Keep these values in the protected deployment
secret store; never commit them.

## Deployment sequence

```sh
docker compose --env-file .env.production \
  -f docker-compose.production.yml build
docker compose --env-file .env.production \
  -f docker-compose.production.yml run --rm migrate
docker compose --env-file .env.production \
  -f docker-compose.production.yml up -d
docker compose --env-file .env.production \
  -f docker-compose.production.yml ps
```

Run exactly one migration process. Take and verify a backup before schema
changes. Do not start API replicas until migration succeeds.

The API command is configurable Gunicorn/Uvicorn. OCR and ML work stays in
Celery. Frontend assets are built once and served by Nginx, never Vite's
development server.

## Network and volumes

PostgreSQL and Redis have no published ports. Only the edge Nginx publishes
HTTP/HTTPS. The private network is internal. Required persistent volumes are
`postgres_data`, `postgres_backups`, `redis_data`, `document_storage`, and
optionally `clamav_data`.

Containers run non-root where their upstream image supports it, drop
capabilities, enable `no-new-privileges`, and use read-only roots plus bounded
`tmpfs` where practical.

## Rollback

Keep the prior immutable images and migration compatibility notes. If a
deployment fails, stop new workers, roll back application images, and downgrade
only when the migration documentation confirms data-safe reversal. Restore from
the last tested backup when downgrade cannot preserve data.
