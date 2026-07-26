#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: ALLOW_RESTORE=true RESTORE_DATABASE=<isolated-db> $0 <backup.dump>" >&2
  exit 2
fi
if [ "${ALLOW_RESTORE:-false}" != "true" ]; then
  echo "Refusing restore: set ALLOW_RESTORE=true after verifying the target." >&2
  exit 3
fi

BACKUP_FILE="$1"
HASH_FILE="${BACKUP_FILE}.sha256"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
RESTORE_DATABASE="${RESTORE_DATABASE:-document_compliance_restore_test}"

test -f "${BACKUP_FILE}"
test -f "${HASH_FILE}"
sha256sum -c "${HASH_FILE}"

case "${RESTORE_DATABASE}" in
  ""|postgres|template0|template1|document_compliance)
    echo "Refusing unsafe restore target: ${RESTORE_DATABASE}" >&2
    exit 4
    ;;
esac

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  sh -ec 'dropdb --if-exists --username="$POSTGRES_USER" "$1"; createdb --username="$POSTGRES_USER" "$1"' \
  restore "${RESTORE_DATABASE}"

docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  sh -ec 'pg_restore --exit-on-error --no-owner --no-acl --username="$POSTGRES_USER" --dbname="$1"' \
  restore "${RESTORE_DATABASE}" < "${BACKUP_FILE}"

TABLE_COUNT="$(docker compose -f "${COMPOSE_FILE}" exec -T postgres \
  sh -ec 'psql --username="$POSTGRES_USER" --dbname="$1" --tuples-only --no-align --command="select count(*) from information_schema.tables where table_schema = '\''public'\'';"' \
  restore "${RESTORE_DATABASE}")"
test "${TABLE_COUNT}" -gt 0
printf 'Restore verified in isolated database %s (%s public tables).\n' \
  "${RESTORE_DATABASE}" "${TABLE_COUNT}"
