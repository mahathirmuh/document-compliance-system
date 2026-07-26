# Security hardening

## Secrets and encryption

Runtime secrets are resolved through the secret-provider abstraction. The
environment provider is implemented for baseline deployments; Azure Key Vault
is optional. Source control, images, database rows, audit metadata, and logs
must never contain raw credentials.

Delta links and webhook client state use authenticated AES-256-GCM encryption
with versioned keys. Rotation runs transactionally with dry-run support and does
not print plaintext.

## HTTP controls

- Production CORS lists explicit HTTPS origins and never combines wildcard
  origins with credentials.
- trusted hosts and proxy networks are configured explicitly;
- client IP forwarding is honored only from trusted proxies;
- sensitive endpoints use Redis-backed user/IP rate limiting;
- request IDs are bounded UUIDs and propagated to jobs and Graph;
- HSTS is enabled only after HTTPS is stable;
- CSP excludes `unsafe-eval`.

## Logging

Production logs are structured JSON. Recursive redaction covers authorization,
cookies, passwords, secrets, tokens, certificate passwords, webhook URLs,
Telegram credentials, and delta links. Document/OCR text and connection strings
are excluded.

## Files

Uploaded files remain private. When malware scanning is enabled, production
uses fail-closed behavior: unavailable scanners keep files quarantined.
Quarantined files cannot be downloaded, extracted, validated, or synchronised
by ordinary users.

## Verification

CI runs Ruff, mypy, Bandit, pip-audit, npm audit, secret scanning, and Trivy.
High/critical findings require review before production approval. A successful
build alone is not a security approval.

