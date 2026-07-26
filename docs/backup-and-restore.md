# Backup and restore

Backups cover PostgreSQL and private local storage. Redis is operational state,
not the durable source of truth. SharePoint is not a replacement for database
or local-history backups.

## PostgreSQL backup

```sh
BACKUP_ROOT=/protected/backups/postgres \
  ./scripts/backup_postgres.sh
```

The script creates a custom-format `pg_dump` and SHA-256 sidecar without placing
the password on the command line. Encrypt and replicate the backup according to
organizational policy.

## Restore test

Restore into an isolated database, never over production:

```sh
ALLOW_RESTORE=true \
RESTORE_DATABASE=document_compliance_restore_test \
  ./scripts/restore_postgres.sh /protected/backups/postgres/backup.dump
```

The script verifies the checksum before restore and confirms that the restored
database contains public tables. Application-level smoke checks and migration
status must then run against the isolated database.

## File storage

Back up relative storage keys and content together. Export a manifest containing
`storageKey` and `sha256`, then verify:

```sh
python scripts/verify_storage_hashes.py \
  --storage-root /srv/document-compliance/storage \
  --manifest /protected/backups/storage-manifest.jsonl
```

Record each restore exercise, date, backup identifier, database/table counts,
storage mismatch count, operator, and approval. A backup is not considered
successful until its restore test passes.

