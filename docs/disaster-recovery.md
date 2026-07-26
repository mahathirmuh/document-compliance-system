# Disaster recovery

RPO and RTO are organization decisions and remain:

- **RPO:** `STAKEHOLDER_DECISION_REQUIRED`
- **RTO:** `STAKEHOLDER_DECISION_REQUIRED`

## Recovery order

1. Declare the incident and prevent writes.
2. Recover the secret provider, encryption keys, and TLS identity.
3. Restore PostgreSQL into an isolated environment and verify integrity.
4. Restore private storage with the original relative keys; verify hashes.
5. Start Redis as empty operational state unless an approved snapshot is used.
6. Run the single Alembic migration job.
7. Start API, then extraction/OCR/language/compliance/quality/report workers.
8. Start SharePoint, notification, maintenance workers and Celery Beat.
9. Validate Graph authentication, selected-site permission, drive, and root.
10. Run SharePoint reconciliation before enabling scheduled/delta sync.
11. Verify notifications, health, metrics, queues, and representative documents.
12. Reopen traffic after incident approval.

## Integrity checks

- Alembic head matches the release.
- application and storage table counts are plausible;
- sampled `DocumentFile` hashes match stored objects;
- encrypted integration state decrypts with the expected key version;
- no duplicate active sync jobs/subscriptions exist;
- reports and audit history remain readable;
- Graph reconciliation accounts for remote items and versions.

If validation fails, stop writes, retain evidence, roll back to the previous
known-good images, and restore the prior tested backup. Communicate impact and
recovery status through the organization's incident process.

