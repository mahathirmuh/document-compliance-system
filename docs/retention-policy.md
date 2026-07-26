# Data retention

Retention policies are scoped by entity and optionally department/document
type. Supported entities include temporary uploads, report snapshots, job
results, notifications, audit logs, deleted files, extraction/OCR histories,
sync history, and webhook events.

## Safety rules

- Cleanup defaults to dry-run and reports candidates/counts/bytes.
- Execution is batched and audit logged.
- Legal hold always wins.
- Documents, revisions, findings, glossary history, and audit logs are never
  permanently deleted without an explicit approved policy.
- Deleted files are soft-deleted before permanent cleanup where applicable.
- A local file is not removed when it is the only copy unless policy explicitly
  permits it.
- Remote delete detection follows the sync profile delete policy; it never
  triggers an implicit hard delete.

Recommended initial policy:

| Entity | Suggested review point |
|---|---|
| Temporary upload | 24 hours |
| Report snapshot | 30 days |
| Webhook event | 30–90 days |
| Notification | 90 days |
| Job result | 90 days |
| Audit log | organization/legal decision |
| Deleted file | organization/legal decision |

These values are examples, not organizational approvals. Administrators should
run dry-run, obtain owner/legal approval, then enable policy execution.

