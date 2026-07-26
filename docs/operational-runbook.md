# Operational runbook

All commands assume the repository root and a protected `.env.production`.

## Start, stop, and status

```sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml down
```

Check `/health/live`, `/health/ready`, `/api/v1/health/dependencies`, and the
authenticated System Health page. Inspect queue depth/heartbeat before
restarting workers. Do not use live Celery inspect for every frontend request.

## Dead-letter recovery

Open **Administration → Background Jobs**, inspect sanitized error and retry
history, correct the root cause, then retry once through the admin API. Dismiss
only with a reason. Never place credentials or full webhook payloads in retry
arguments.

## Graph and SharePoint

- **Test connection:** verify token, selected site, drive, and root separately.
- **429:** honor `Retry-After`, lower worker concurrency, stop manual retries,
  and mark the connection degraded if sustained.
- **Renew subscription:** run the administrative renewal action; verify only one
  active remote subscription and new expiry.
- **Reset delta:** provide a confirmation reason, invalidate encrypted state,
  and run reconciliation. Never paste a delta link into logs/tickets.
- **Reconcile:** pause the profile, run reconciliation, review conflicts, then
  resume scheduled sync.
- **Compromised integration:** disable the connection/profile, revoke Entra
  credential and selected-site access, rotate secrets/keys, inspect audit and
  webhook history, then create a new credential.

## Conflict resolution

Assign the conflict, compare local/remote evidence, select a resolution, enter a
mandatory comment, and confirm the resulting local/remote versions. Manual
policy never permits automatic overwrite.

## Capacity and dependencies

- **Storage full:** stop uploads/sync, preserve active jobs, expand storage or
  run an approved retention dry-run, then resume.
- **Database unavailable:** stop write workers, restore database service, check
  Alembic head and connection pool, then resume queues.
- **Redis unavailable:** preserve database job state, restore Redis, and
  requeue only idempotent jobs.
- **Worker heartbeat stale:** inspect container health/logs, drain the worker,
  restart it, and reconcile jobs left in active states.

## Quarantine

Quarantined files stay unavailable to ordinary users and cannot enter extraction
or SharePoint sync. A security administrator reviews scanner evidence and either
retains/deletes under policy or re-scans after signature/service recovery.

## Backup and restore

Run `scripts/backup_postgres.sh`, verify its SHA-256 sidecar, back up private
storage, and record the backup ID. Restore only to an isolated database using
`ALLOW_RESTORE=true`; verify tables, migration, hashes, and application smoke
tests before declaring success.

## Credential rotation

Rotate client secrets/certificates with overlap: install the new credential,
test Graph, switch active configuration, restart safely, then revoke the old
credential. Encryption-key rotation starts with dry-run, takes a backup, updates
rows transactionally, validates decryptability, and only then retires the old
key.

## Rollback

Drain traffic and workers, retain logs/metrics/audit evidence, restore previous
immutable images, and downgrade schema only when the migration explicitly
supports a data-safe downgrade. Otherwise restore the last tested backup.
