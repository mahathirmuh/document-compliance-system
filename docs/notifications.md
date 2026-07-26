# Notifications

Application events are evaluated against scoped rules, recipients are resolved
from trusted application records, templates are rendered in a sandbox, and
delivery jobs are sent through channel adapters.

Supported channels:

- `IN_APP`
- `EMAIL_GRAPH`
- `TEAMS`
- `TELEGRAM`

All remote channels are disabled by default. Graph email uses a fixed sender
mailbox; Teams and Telegram credentials remain in the secret provider.

## Templates and safety

Templates are versioned per event/channel/language and allow only registered
variables. Arbitrary Python, JavaScript, attribute access, and untrusted
recipient expressions are rejected. Notification content contains identifiers,
status, bounded summaries, and internal application links—never full document
or OCR text.

## Preferences

Users can enable permitted channels by event and configure digest mode, timezone
and quiet hours. Mandatory security/system rules may bypass preferences only
when explicitly configured and documented.

## Delivery

In-app creation may occur synchronously when lightweight. Remote delivery uses
the `notifications` queue. Transient provider failures receive bounded,
jittered retries; permanent failures are retained in delivery history.
Notification failure does not roll back a successful business transaction.

The notification centre polls at a bounded interval, displays an unread count,
and supports individual/read-all operations. Action URLs must be validated
internal routes to prevent open redirects.
