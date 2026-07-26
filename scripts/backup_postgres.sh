#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-./backups/postgres}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_ROOT}/document-compliance-${STAMP}.dump"
HASH_FILE="${BACKUP_FILE}.sha256"

mkdir -p "${BACKUP_ROOT}"
umask 077

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  sh -ec 'pg_dump --format=custom --no-owner --no-acl --username="$POSTGRES_USER" "$POSTGRES_DB"' \
  > "${BACKUP_FILE}"

test -s "${BACKUP_FILE}"
sha256sum "${BACKUP_FILE}" > "${HASH_FILE}"
printf 'Backup created: %s\nIntegrity file: %s\n' "${BACKUP_FILE}" "${HASH_FILE}"
