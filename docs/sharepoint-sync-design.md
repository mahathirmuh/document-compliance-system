# SharePoint synchronisation design

The internal document, revision, and `DocumentFile` records remain the business
source of truth. SharePoint versions are storage versions and do not replace
business revisions.

## Directions

- `OUTBOUND`: local application data drives file and mapped metadata changes.
- `INBOUND`: SharePoint changes create or update internal history.
- `BIDIRECTIONAL`: both sides may change; a non-empty conflict policy is
  mandatory and defaults to `MANUAL`.

Delete policies are limited to ignore, archive local, mark missing, or local
soft-delete. Synchronisation never hard-deletes document history.

## Transaction boundaries

Jobs and claimed items are committed before network I/O. Graph transfers occur
without an open database transaction. Results are persisted in short
transactions with optimistic eTag/hash checks.

## Full and incremental sync

Full sync enumerates the configured root and reconciles it with scoped internal
records. Incremental sync:

1. decrypts the stored delta link;
2. follows every `@odata.nextLink`;
3. builds idempotent sync items;
4. detects deletions and conflicts;
5. processes each item with bounded retry; and
6. persists the new encrypted delta link only after policy-compliant success.

An invalid delta token is marked invalid and queues controlled reconciliation.
It is never silently replaced before changes are processed.

## Idempotency

The idempotency identity combines profile, remote item ID, remote eTag, local
SHA-256 hash, and operation. Webhook payload hashes prevent duplicate events
from creating duplicate documents, revisions, or files.

## Webhooks

The validation handshake returns `validationToken` as plain text. Normal
notifications require a valid hashed client state, are persisted/deduplicated,
and only queue Celery work. Heavy sync never runs in the webhook request.

Subscriptions are renewed by Celery Beat before expiry. Renewal failures create
an administrator notification and retain diagnostic request IDs without tokens.

