# Document Compliance & Multilingual Validation System

Version 1.0.0 completes Phase 10 of the foundation for a Document Control
application that registers document metadata and revisions, stores their
private physical files, extracts normalized PDF, DOCX, and XLSX content,
performs local OCR on scanned PDF pages, detects Indonesian, English, and
Mandarin content, validates multilingual structural compliance, and connects
controlled files to SharePoint Online through backend-only Microsoft Graph
synchronisation. It remains deliberately non-destructive and does not edit
source-document content.

Phase 1 established the React, FastAPI, async SQLAlchemy, Alembic, PostgreSQL,
and Docker foundation. Phase 2 added authentication, authorization, and the
protected application shell. Phase 3 added audited Master Data management and
XLSX import/export. Phase 4 added the department-scoped Document Register,
revision history, archive/restore, and audited register import/export. Phase 5
adds secure PDF, DOCX, and XLSX upload, automatic register identification,
private storage, file history, and controlled download.
Phase 6 adds a durable Celery/Redis extraction queue, format-specific
extractors, normalized content persistence, history, search, and JSON/TXT
export.
Phase 7 adds separate local OCR and language-detection workers, retained OCR
provenance and confidence, hybrid Unicode/fastText language detection, and
preliminary block/container/document language coverage.
Phase 8 adds retained compliance jobs and runs, rule snapshots, canonical
section matching, structural translation groups, language-order and table
checks, weighted scoring, auditable findings, comparison, and reports.
Phase 9 adds local pairwise translation-similarity signals, scoped glossary
management and validation, retained revision comparisons, private advanced
report snapshots, and an explicit quality-score strategy.
Phase 10 adds Microsoft Graph client-credentials authentication, SharePoint
storage and mapping, full/delta/webhook synchronisation, manual conflict
resolution, multi-channel notifications, and production security,
observability, retention, backup, and deployment controls.

## Scope through Phase 10

Implemented in this phase:

- Two-stage single and batch uploads: temporary preview, identification, and
  explicit confirmation
- Streaming size enforcement, filename sanitisation, MIME/extension/signature
  consistency checks, bounded OOXML inspection, and SHA-256 duplicate detection
- Automatic matching to an existing revision, a new revision, or a new
  document, with manual correction before confirmation
- Provider-neutral storage with a private local provider and opaque relative
  object keys
- Department-scoped attachment, metadata/history, authenticated download,
  replacement, soft delete, and explicit restore
- Expiring upload sessions plus an idempotent cleanup command for temporary
  objects
- Permission-aware frontend upload, batch, history, document-file, and revision
  file views
- Audit records for upload previews/confirmation, duplicate/quarantine events,
  downloads, replacement, deletion/restoration, and cleanup
- Durable extraction jobs with progress, controlled errors, cancellation,
  retries for transient infrastructure failures, and retained re-extraction
  history
- PDF page/text-block/bounding-box extraction and scan detection without
  claiming OCR
- Ordered DOCX paragraphs, headings, tables, cells, headers, and footers
- Read-only XLSX worksheet, non-empty cell, formula text, cached-value
  metadata, and merged-range extraction without formula execution
- A unified container/block/table model, deterministic content hashes, latest
  result references, server-side pagination, plain-text search, and bounded
  JSON/TXT export
- Permission-aware extraction queue, history, document/revision content
  viewers, search, re-extraction, cancellation, and export UI
- PDF-only OCR with 300 DPI PyMuPDF rendering, bounded image dimensions,
  `NONE`/`STANDARD`/`AGGRESSIVE` OpenCV preprocessing, rotation/deskew support,
  PaddleOCR Latin, Simplified Chinese, and automatic multilingual profiles
- Page-level OCR selection that preserves native selectable text, retained
  OCR jobs/runs/pages/blocks, bounding boxes, confidence, history, re-OCR,
  cancellation, and JSON/TXT export
- Hybrid local language detection using Unicode script statistics, fastText
  `lid.176`, Indonesian/English lexical signals, short-text eligibility,
  mixed-language rules, and distinct `unknown`/`other` outcomes
- Retained block decisions and container summaries with source provenance,
  confidence, language presence, block coverage, character coverage, history,
  re-detection, cancellation, and JSON/XLSX export
- Separate `extraction`, `ocr`, and `language` queues plus dependency readiness
  reporting that does not load inference models
- Permission-aware OCR queue/history/results and language-detection/result
  pages integrated into document detail and extracted-content workflows
- Background compliance validation over compatible extraction, OCR, and
  language-detection sources without rereading or modifying source binaries
- Backward-compatible validation-rule controls for required languages,
  coverage, sections, ordering, grouping, tables, scoring, penalties, and caps
- Canonical section profiles and Indonesian, English, Mandarin, or
  language-neutral aliases with confidence-aware and regex-bounded matching
- PDF positional, DOCX paragraph/table, and XLSX row/column structural
  translation grouping without semantic-equivalence claims
- Immutable compliance history, rule snapshots, score breakdowns, revalidation
  comparisons, bounded JSON/XLSX exports, and department-scoped reports
- Auditable finding generation, manual findings, assignment, review,
  resolution, false-positive, accepted-risk, and reopen workflows
- Separate `compliance` Celery queue and worker readiness reporting
- Local multilingual embeddings for Indonesian–English,
  Indonesian–Chinese, and English–Chinese translation-group comparisons
- Confidence-aware similarity categories, bounded long-text chunking, and
  number/date/measurement/reference/negation consistency signals
- Department/document-type scoped glossary profiles, translations, variants,
  reasoned exceptions, preview/confirm import, and scoped XLSX/JSON export
- Background glossary validation with retained matches, history, findings,
  cancellation, revalidation, and bounded export
- Non-destructive comparison of retained document revisions, including
  structural/language/compliance/similarity/finding changes
- Advanced XLSX/JSON/PDF report generation, private expiring snapshots,
  authenticated download, and manually executable schedule configurations
- Separate `similarity`, `glossary`, `revision-comparison`, and `reporting`
  Celery queues plus dependency readiness reporting
- A default separate quality score that preserves historical compliance
  scores/statuses and stores the selected mode and weight snapshot

All Phase 1 health, Phase 2 authentication, Phase 3 Master Data, and Phase 4
Document Register behavior and Phase 5 physical-file workflows remain
available. Similarity remains a review signal rather than proof of translation
correctness. Automatic translation, source editing, cloud AI, scheduled email
delivery, full approval workflows, antivirus claims, and SharePoint API
synchronization remain intentionally unimplemented.

## Architecture

```text
Browser
  |
  v
React + Vite (local port 5173)
or nginx (container port 80, published as 5173)
  |
  | /api/v1
  v
FastAPI (port 8000)
  |-- JWT authentication and backend role guards
  |-- Master Data services and audited XLSX import/export
  |-- Document Register, Revision, and Physical File services
  |-- Signature, OOXML safety, SHA-256, and identification services
  |-- Extraction job, content query, search, and export services
  |-- Endpoint -> Service -> Repository -> Database
  |                         |
  v                         v
PostgreSQL 16             Redis 7
  ^                         |
  |                         v
  +------ Celery extraction worker (queue: extraction)
  |         |-- PDF / DOCX / XLSX extractor factory
  |         +-- normalized result persistence
  +------ Celery OCR worker (queue: ocr, concurrency: 1)
  |         |-- local PaddleOCR Latin / Simplified Chinese
  |         +-- PDF render, preprocess, recognize, merge, persist
  +------ Celery language worker (queue: language)
  |         |-- local Unicode + fastText hybrid detector
  +------ Celery compliance worker (queue: compliance)
  |         |-- section/group validators, score, findings, persistence
  |         +-- block/container coverage aggregation
  +------ Celery similarity worker (queue: similarity, concurrency: 1)
  |         |-- local multilingual sentence-transformer
  |         +-- pairwise score/confidence + deterministic consistency checks
  +------ Celery glossary worker (queue: glossary)
  |         +-- scoped term matching, exceptions, findings, persistence
  +------ Celery revision worker (queue: revision-comparison)
  |         +-- retained alignment and change comparison
  +------ Celery reporting worker (queue: reporting, concurrency: 1)
            +-- bounded private XLSX/JSON/PDF snapshots

FastAPI + workers ---> ./storage/documents (private persistent bind mount)
OCR/language/similarity workers -> ./models (local read-only inference inputs)
```

The frontend may hide navigation by role, but this is only a usability layer.
The backend remains the source of truth for every protected operation.

PostgreSQL stores file metadata and upload-session state; binaries remain in
private provider storage and are never served as public static files.

## Technology stack

| Layer       | Technology                                                                          |
| ----------- | ----------------------------------------------------------------------------------- |
| Frontend    | React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Zustand, Axios |
| Backend     | Python 3.12, FastAPI, Pydantic, JWT authentication                                  |
| Data access | SQLAlchemy 2.0 async, asyncpg, Alembic                                              |
| Database    | PostgreSQL 16                                                                       |
| Extraction  | Celery, Redis, PyMuPDF, python-docx, openpyxl                                       |
| OCR         | PaddleOCR, PaddlePaddle, OpenCV headless, Pillow                                    |
| Language    | fastText `lid.176`, Unicode script and deterministic lexical rules                  |
| Similarity  | sentence-transformers, PyTorch, scikit-learn, RapidFuzz (local CPU by default)       |
| Reporting   | openpyxl, ReportLab, private provider-backed snapshots                              |
| Development | Docker, Docker Compose, ESLint, Prettier, Vitest, Pytest, Ruff                      |

## Roles

Phase 2 defines the complete role vocabulary used by later features:

| Role                  | Intended access                                                                                            |
| --------------------- | ---------------------------------------------------------------------------------------------------------- |
| `SUPER_ADMIN`         | Full administration, users, roles, master data, settings, audit logs, and document archive/delete controls |
| `DOCUMENT_CONTROLLER` | Document register, uploads, validation, metadata, findings, reviewer assignment, and reports               |
| `REVIEWER`            | Assigned documents, comments, approval/rejection, false positives, and finding closure                     |
| `DEPARTMENT_USER`     | Department-scoped upload, document and finding access, and corrected revisions                             |
| `AUDITOR`             | Read-only reports, audit trail, and exports                                                                |
| `VIEWER`              | Read-only access to explicitly permitted data                                                              |

Master Data access uses the existing Phase 2 permission vocabulary:

| Permission           | Capability                                      |
| -------------------- | ----------------------------------------------- |
| `master_data:view`   | Open the overview, lists, options, and exports  |
| `master_data:create` | Create records and confirm create-only imports  |
| `master_data:update` | Edit records, set defaults, and confirm upserts |
| `master_data:delete` | Activate or deactivate records                  |

`SUPER_ADMIN` receives all four permissions. `DOCUMENT_CONTROLLER` retains
read-only `master_data:view` access from the Phase 2 mapping. Backend
dependencies are authoritative; hidden frontend controls are only a UX layer.

Document Register authorization is also defined in the same backend mapping:

| Permission                       | Capability                                         |
| -------------------------------- | -------------------------------------------------- |
| `documents:view`                 | View register records allowed by department scope  |
| `documents:create`               | Create document metadata and an initial revision   |
| `documents:update`               | Update allowed document metadata                   |
| `documents:archive`              | Archive a document with a reason                   |
| `documents:restore`              | Restore an archived document                       |
| `documents:export`               | Export the accessible register rows                |
| `documents:import`               | Preview and confirm register XLSX imports          |
| `documents:view_all_departments` | Bypass the default `document.department_id` scope  |
| `documents:manage_revisions`     | Add, edit, select, or supersede document revisions |

`SUPER_ADMIN` and `DOCUMENT_CONTROLLER` receive the complete Document Register
set. `DEPARTMENT_USER` receives view/create/update but remains locked to the
department on the user profile. `AUDITOR` receives read-only view/export across
departments. `REVIEWER` and `VIEWER` receive scoped read-only access. Every API
operation enforces these rules again even when the frontend hides a control.

Physical-file authorization extends the same centralized mapping:

| Permission                    | Capability                                      |
| ----------------------------- | ----------------------------------------------- |
| `documents:upload`            | Preview and confirm a single physical file      |
| `documents:download`          | Download an accessible available/current file   |
| `documents:replace_file`      | Replace a current file while retaining history  |
| `documents:delete_file`       | Soft-delete and explicitly restore a file       |
| `documents:batch_upload`      | Preview and confirm multi-file batches          |
| `documents:view_file_history` | View replaced/deleted file metadata and history |

`SUPER_ADMIN` and `DOCUMENT_CONTROLLER` receive all six.
`DEPARTMENT_USER` receives upload, download, and scoped history.
`REVIEWER` receives scoped download/history; `AUDITOR` receives
cross-department download/history; and `VIEWER` receives scoped current-file
download only.

Phase 7 authorization remains in the same backend mapping:

| Permission                          | Capability                                     |
| ----------------------------------- | ---------------------------------------------- |
| `documents:ocr`                     | Queue OCR for an eligible current PDF          |
| `documents:reocr`                   | Queue a retained re-OCR run                    |
| `documents:view_ocr_results`        | Read OCR runs, pages, blocks, and safe exports |
| `documents:view_ocr_history`        | Read retained OCR history                      |
| `documents:cancel_ocr`              | Cooperatively cancel an active OCR job         |
| `documents:detect_language`         | Queue language detection for extracted content |
| `documents:redetect_language`       | Queue a retained language re-detection run     |
| `documents:view_language_results`   | Read language results and preliminary coverage |
| `documents:export_language_results` | Download bounded JSON/XLSX language exports    |

`DOCUMENT_CONTROLLER` receives the complete set. `DEPARTMENT_USER` can queue
initial OCR and language detection only inside its own department.
`REVIEWER`, `AUDITOR`, and `VIEWER` remain read-only as defined by the backend;
the auditor can export accessible language results across departments.
Replaced, deleted, historical, non-PDF, and cross-department files are rejected
by the service even if a client sends a handcrafted request.

Phase 8 adds a separate compliance and finding permission set:

| Permission                         | Capability                                      |
| ---------------------------------- | ----------------------------------------------- |
| `compliance:view`                  | Read accessible jobs, runs, and result details  |
| `compliance:validate`              | Queue initial validation in department scope    |
| `compliance:revalidate`            | Queue an audited retained revalidation           |
| `compliance:view_all_departments`  | Read compliance data across departments          |
| `compliance:export`                | Download bounded compliance exports              |
| `compliance:configure_rules`       | Maintain canonical sections and aliases          |
| `findings:view`                    | Read accessible findings                         |
| `findings:create_manual`           | Create a retained manual finding                 |
| `findings:update`                  | Update permitted finding details                 |
| `findings:review`                  | Move a finding into review                       |
| `findings:resolve`                 | Resolve or accept the risk of a finding          |
| `findings:reopen`                  | Reopen a terminal finding                        |
| `findings:false_positive`          | Mark a finding as a false positive               |
| `findings:export`                  | Download bounded finding exports                 |

The backend applies compliance department scope independently from Document
Register scope. Auditors can read and export across departments but cannot
validate or mutate findings. Viewers remain read-only, department users can
validate only their own department, and only a super administrator or a user
with `compliance:configure_rules` can change section profiles and aliases.
Compliance and finding report pages additionally require the existing
`reports:view` permission; the frontend applies the same guard as the backend.

## Access and refresh token strategy

- Login accepts `email` and `password`.
- A short-lived access token authorizes protected API calls through
  `Authorization: Bearer <token>`.
- A longer-lived refresh token is exchanged only through
  `POST /api/v1/auth/refresh`.
- Phase 2 stores the session and both tokens behind one isolated Zustand
  `localStorage` adapter so a reload can revalidate the session through
  `/auth/me`. Production should move refresh-token persistence to a Secure,
  HttpOnly, SameSite cookie.
- When an access token expires, the frontend attempts a single refresh and then
  retries the original request.
- If refresh fails or the account is inactive, the frontend clears its session
  and returns the user to login.
- Logout calls the backend logout endpoint and clears client authentication
  state.
- Changing `JWT_SECRET_KEY` invalidates tokens signed with the previous key.

Default development lifetimes are 15 minutes for access tokens and 7 days for
refresh tokens. Configure them through environment variables. Never send tokens
in URLs or write them to application logs.

## Prerequisites

The Docker workflow requires:

- Docker Desktop or Docker Engine with Docker Compose v2
- Git

For development without application containers, also install:

- Node.js 22.22 or newer and npm 10 or newer
- Python 3.12 or newer
- PostgreSQL 16 when running the backend directly on the host

## Installation and secrets

Create the local environment file from the repository root:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

Before starting the application, replace all `REPLACE_ME_...` values in `.env`.
Generate the JWT secret with a cryptographically secure generator, for example:

```bash
openssl rand -hex 32
```

Use different values for development, test, staging, and production. Never
commit `.env`, a real JWT secret, a database password, or an administrator
password.

Install the inference models explicitly from the repository root. These
operator-run scripts use the configured official HTTPS sources, reuse an
existing valid file, support optional SHA-256 verification, and never run at
application startup:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\download_ocr_models.py --model-root models/ocr
backend\.venv\Scripts\python.exe backend\scripts\download_language_model.py --path models/language/lid.176.bin
```

Docker mounts the resulting ignored directories as `/app/models/ocr` and
`/app/models/language`. Model binaries must not be committed, returned by an
API, or copied into a public storage directory.

The repository includes generated, company-data-free acceptance fixtures under
`sample-documents/ocr` and `sample-documents/language`. Regenerate the exact
eight PDF and six DOCX/XLSX fixtures from the repository root with:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\generate_phase7_sample_documents.py
```

The scanned PDF fixtures contain image-only Indonesian, English, Simplified
Chinese, mixed-language, rotated, low-resolution, partial-scan, and blank
cases. The language fixtures cover the three target languages, mixed content,
and short or code-like text. They are synthetic and must not be replaced with
internal company documents.

## Environment configuration

| Variable                                  | Example/default              | Purpose                                            |
| ----------------------------------------- | ---------------------------- | -------------------------------------------------- |
| `APP_NAME`                                | `Document Compliance API`    | Backend service name                               |
| `APP_VERSION`                             | `1.0.0`                      | Backend version                                    |
| `VITE_APP_VERSION`                        | `1.0.0`                      | Frontend version                                   |
| `APP_ENV`                                 | `development`                | Backend runtime environment                        |
| `APP_TIMEZONE`                            | `Asia/Makassar`              | IANA timezone used for export timestamps           |
| `BACKEND_DEBUG`                           | `false`                      | Backend debug mode                                 |
| `API_V1_PREFIX`                           | `/api/v1`                    | Versioned API prefix                               |
| `FRONTEND_PORT`                           | `5173`                       | Frontend host port                                 |
| `BACKEND_PORT`                            | `8000`                       | Backend host port                                  |
| `VITE_API_BASE_URL`                       | `/api/v1`                    | Browser-facing API base path                       |
| `VITE_API_URL`                            | `/api/v1`                    | Phase 2 API URL; falls back to `VITE_API_BASE_URL` |
| `VITE_DEV_API_PROXY_TARGET`               | `http://localhost:8000`      | Local Vite proxy target                            |
| `VITE_DOCUMENT_MAX_FILE_SIZE_MB`          | `50`                         | Client-side single-file validation limit           |
| `VITE_DOCUMENT_BATCH_MAX_FILES`           | `50`                         | Client-side batch file-count limit                 |
| `VITE_DOCUMENT_BATCH_MAX_TOTAL_SIZE_MB`   | `500`                        | Client-side aggregate batch limit                  |
| `POSTGRES_DB`                             | `document_compliance`        | Bundled PostgreSQL database                        |
| `POSTGRES_USER`                           | `document_compliance`        | Bundled PostgreSQL user                            |
| `POSTGRES_PASSWORD`                       | replace-required placeholder | Bundled PostgreSQL password                        |
| `DATABASE_NAME`                           | value of `POSTGRES_DB`       | Application database; may target an external DB    |
| `DATABASE_USER`                           | value of `POSTGRES_USER`     | Application database user                          |
| `DATABASE_PASSWORD`                       | value of `POSTGRES_PASSWORD` | Optional separate application database password    |
| `DATABASE_HOST`                           | `postgres`                   | Application PostgreSQL hostname                    |
| `DATABASE_PORT`                           | `5432`                       | Application PostgreSQL port                        |
| `DATABASE_ECHO`                           | `false`                      | SQLAlchemy SQL logging                             |
| `BACKEND_CORS_ORIGINS`                    | `http://localhost:5173`      | Comma-separated allowed origins                    |
| `JWT_SECRET_KEY`                          | replace-required placeholder | JWT signing secret; at least 32 random characters  |
| `JWT_ALGORITHM`                           | `HS256`                      | JWT signing algorithm                              |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`         | `15`                         | Access-token lifetime                              |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`           | `7`                          | Refresh-token lifetime                             |
| `MAX_LOGIN_ATTEMPTS`                      | `5`                          | Failed attempts before temporary lock              |
| `ACCOUNT_LOCK_MINUTES`                    | `15`                         | Temporary lock duration                            |
| `DEFAULT_ADMIN_NAME`                      | `System Administrator`       | Seeded administrator name                          |
| `DEFAULT_ADMIN_EMAIL`                     | `admin@example.com`          | Seeded administrator login email                   |
| `DEFAULT_ADMIN_PASSWORD`                  | replace-required placeholder | Seeded administrator password                      |
| `STORAGE_PROVIDER`                        | `local`                      | Private storage provider                           |
| `STORAGE_ROOT`                            | `./storage`                  | Host-run private storage root                      |
| `STORAGE_DOCUMENTS_PREFIX`                | `documents/originals`        | Confirmed physical files                           |
| `STORAGE_TEMP_PREFIX`                     | `documents/temporary`        | Unconfirmed upload objects                         |
| `STORAGE_QUARANTINE_PREFIX`               | `documents/quarantine`       | Invalid security-validation objects                |
| `STORAGE_DELETED_PREFIX`                  | `documents/deleted`          | Soft-deleted physical files                        |
| `DOCUMENT_MAX_FILE_SIZE_MB`               | `50`                         | Maximum physical file size                         |
| `DOCUMENT_BATCH_MAX_FILES`                | `50`                         | Maximum files per batch                            |
| `DOCUMENT_BATCH_MAX_TOTAL_SIZE_MB`        | `500`                        | Maximum aggregate batch size                       |
| `ALLOWED_DOCUMENT_EXTENSIONS`             | `.pdf,.docx,.xlsx`           | Exact physical-file extension allowlist            |
| `ENABLE_FILE_SIGNATURE_VALIDATION`        | `true`                       | Verify PDF/OOXML signatures and structures         |
| `ENABLE_DUPLICATE_FILE_HASH_CHECK`        | `true`                       | Compare streaming SHA-256 hashes                   |
| `ENABLE_FILE_QUARANTINE`                  | `true`                       | Retain rejected security-validation objects        |
| `FILE_DOWNLOAD_CHUNK_SIZE_KB`             | `1024`                       | Backend download streaming chunk size              |
| `TEMP_FILE_RETENTION_HOURS`               | `24`                         | Upload-session and temporary-object retention      |
| `CELERY_BROKER_URL`                       | `redis://redis:6379/0`       | Durable extraction task broker                     |
| `CELERY_RESULT_BACKEND`                   | `redis://redis:6379/1`       | Short-lived Celery task result backend             |
| `EXTRACTION_QUEUE_NAME`                   | `extraction`                 | Dedicated extraction queue                         |
| `EXTRACTION_WORKER_CONCURRENCY`           | `2`                          | Compose worker process concurrency                 |
| `EXTRACTION_MAX_FILE_SIZE_MB`             | `50`                         | Worker-side extraction file limit                  |
| `EXTRACTION_TASK_TIME_LIMIT_SECONDS`      | `1800`                       | Celery hard task limit                             |
| `EXTRACTION_TASK_SOFT_TIME_LIMIT_SECONDS` | `1500`                       | Controlled timeout threshold                       |
| `EXTRACTION_MAX_RETRIES`                  | `2`                          | Transient worker retry count                       |
| `EXTRACTION_DB_BATCH_SIZE`                | `1000`                       | Persistence batch size                             |
| `PDF_MAX_PAGES`                           | `5000`                       | Maximum PDF pages                                  |
| `PDF_MIN_CHARACTERS_PER_PAGE`             | `20`                         | Scan-detection text threshold                      |
| `PDF_SCANNED_PAGE_RATIO_THRESHOLD`        | `0.7`                        | Ratio that produces `OCR_REQUIRED`                 |
| `DOCX_MAX_PARAGRAPHS`                     | `500000`                     | Maximum DOCX paragraphs                            |
| `DOCX_MAX_TABLES`                         | `10000`                      | Maximum DOCX tables                                |
| `DOCX_MAX_TABLE_CELLS`                    | `2000000`                    | Maximum DOCX logical table cells                   |
| `XLSX_MAX_WORKSHEETS`                     | `200`                        | Maximum workbook worksheets                        |
| `XLSX_MAX_ROWS_PER_SHEET`                 | `200000`                     | Maximum worksheet row boundary                     |
| `XLSX_MAX_CELLS_PER_WORKBOOK`             | `2000000`                    | Maximum non-empty workbook cells                   |
| `XLSX_MAX_FORMULAS`                       | `500000`                     | Maximum stored formulas                            |
| `EXTRACTION_EXPORT_MAX_BLOCKS`            | `2000000`                    | Maximum blocks in one export                       |
| `EXTRACTION_SEARCH_MAX_RESULTS`           | `500`                        | Maximum plain-text search matches                  |
| `MASTER_DATA_IMPORT_MAX_ROWS`             | `5000`                       | Maximum data rows accepted by one XLSX import      |
| `MASTER_DATA_EXPORT_MAX_ROWS`             | `50000`                      | Maximum rows emitted by one Master Data export     |
| `DEFAULT_COMPANY_CODE`                    | `MTI`                        | Default company component for document codes       |
| `DOCUMENT_REGISTER_IMPORT_MAX_ROWS`       | `10000`                      | Maximum register rows accepted by one XLSX import  |
| `DOCUMENT_REGISTER_EXPORT_MAX_ROWS`       | `100000`                     | Maximum rows emitted by one register export        |
| `DOCUMENT_IMPORT_MAX_FILE_SIZE_MB`        | `25`                         | Maximum register workbook upload size              |
| `DOCUMENT_NUMBER_MAX_LENGTH`              | `50`                         | Maximum normalized document-number length          |
| `DOCUMENT_TITLE_MAX_LENGTH`               | `500`                        | Maximum document-title length                      |
| `ARCHIVE_REASON_MAX_LENGTH`               | `1000`                       | Maximum archive-reason length                      |

Phase 7 inference and worker limits:

| Variable                                                  | Default                            | Purpose                                                 |
| --------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------- |
| `OCR_QUEUE_NAME`                                          | `ocr`                              | Dedicated OCR queue                                     |
| `LANGUAGE_QUEUE_NAME`                                     | `language`                         | Dedicated language queue                                |
| `OCR_WORKER_CONCURRENCY`                                  | `1`                                | OCR processes per worker                                |
| `LANGUAGE_WORKER_CONCURRENCY`                             | `2`                                | Language processes per worker                           |
| `OCR_PROVIDER`                                            | `paddleocr`                        | Local OCR provider                                      |
| `OCR_MODEL_ROOT`                                          | `/app/models/ocr`                  | Mounted OCR model root                                  |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`                   | `True`                             | Disable Paddle model-host connectivity check            |
| `OCR_AUTO_MULTILINGUAL_CHINESE_PASS`                      | `true`                             | Enable the bounded Chinese pass for `AUTO_MULTILINGUAL` |
| `OCR_AUTO_MULTILINGUAL_CHINESE_PASS_CONFIDENCE_THRESHOLD` | `0.65`                             | Confidence trigger for Chinese second pass              |
| `OCR_AUTO_MULTILINGUAL_CHINESE_PASS_MINIMUM_CHARACTERS`   | `20`                               | Text-length trigger for Chinese second pass             |
| `OCR_RENDER_DPI`                                          | `300`                              | PDF render density                                      |
| `OCR_MAX_RENDER_WIDTH` / `HEIGHT`                         | `6000`                             | Render dimension guards                                 |
| `OCR_MAX_PAGES_PER_JOB`                                   | `500`                              | Page-count guard                                        |
| `OCR_MAX_CONCURRENT_JOBS_PER_USER`                        | `3`                                | Per-requester active-job limit                          |
| `OCR_TASK_TIME_LIMIT_SECONDS`                             | `3600`                             | Celery hard limit                                       |
| `OCR_TASK_SOFT_TIME_LIMIT_SECONDS`                        | `3300`                             | Controlled timeout threshold                            |
| `OCR_MAX_RETRIES`                                         | `1`                                | Transient OCR retry count                               |
| `OCR_LOW_CONFIDENCE_THRESHOLD`                            | `0.60`                             | Low-confidence classification                           |
| `OCR_REVIEW_CONFIDENCE_THRESHOLD`                         | `0.80`                             | Review indicator threshold                              |
| `OCR_SKIP_PAGES_WITH_SELECTABLE_TEXT`                     | `true`                             | Preserve native page text                               |
| `OCR_SELECTABLE_TEXT_MIN_CHARACTERS`                      | `50`                               | Native-text page threshold                              |
| `OCR_DEFAULT_PREPROCESSING_PROFILE`                       | `STANDARD`                         | Default image preprocessing                             |
| `LANGUAGE_MODEL_PATH`                                     | `/app/models/language/lid.176.bin` | Mounted fastText model                                  |
| `LANGUAGE_CONFIDENCE_MINIMUM`                             | `0.55`                             | Minimum classified-language confidence                  |
| `LANGUAGE_CONFIDENCE_REVIEW_THRESHOLD`                    | `0.75`                             | Low-confidence review indicator                         |
| `LANGUAGE_HAN_CHARACTER_RATIO_THRESHOLD`                  | `0.20`                             | Strong Mandarin candidate threshold                     |
| `LANGUAGE_MIXED_SECONDARY_SCORE_THRESHOLD`                | `0.25`                             | Secondary mixed-language signal threshold               |
| `LANGUAGE_MIXED_MIN_CHARACTER_RATIO`                      | `0.15`                             | Han/Latin mixed-script ratio                            |
| `LANGUAGE_PRESENCE_MIN_BLOCKS`                            | `2`                                | Minimum language-presence block evidence                |
| `LANGUAGE_PRESENCE_MIN_CHARACTERS`                        | `20`                               | Minimum language-presence character evidence            |
| `LANGUAGE_DETECTION_DB_BATCH_SIZE`                        | `1000`                             | Language result insert batch                            |
| `LANGUAGE_DETECTION_MAX_BLOCKS`                           | `2000000`                          | Detection guard                                         |
| `LANGUAGE_EXPORT_MAX_BLOCKS`                              | `2000000`                          | Export guard                                            |
| `LANGUAGE_TASK_TIME_LIMIT_SECONDS`                        | `1800`                             | Celery hard limit                                       |
| `LANGUAGE_TASK_SOFT_TIME_LIMIT_SECONDS`                   | `1500`                             | Controlled timeout threshold                            |
| `AUTO_RUN_OCR_AFTER_EXTRACTION`                           | `false`                            | Optional pipeline chaining                              |
| `AUTO_RUN_LANGUAGE_DETECTION_AFTER_EXTRACTION`            | `false`                            | Optional pipeline chaining                              |
| `AUTO_RUN_LANGUAGE_DETECTION_AFTER_OCR`                   | `false`                            | Optional pipeline chaining                              |

Phase 8 validation, matching, and export limits:

| Variable                                      | Default      | Purpose                                              |
| --------------------------------------------- | ------------ | ---------------------------------------------------- |
| `COMPLIANCE_QUEUE_NAME`                       | `compliance` | Dedicated compliance queue                           |
| `COMPLIANCE_WORKER_CONCURRENCY`               | `2`          | Compliance processes per worker                      |
| `COMPLIANCE_MAX_BLOCKS`                       | `2000000`    | Maximum source blocks in one validation context      |
| `COMPLIANCE_MAX_TRANSLATION_GROUPS`           | `500000`     | Maximum structural groups per run                    |
| `COMPLIANCE_DB_BATCH_SIZE`                    | `1000`       | Compliance result persistence batch size             |
| `COMPLIANCE_TASK_TIME_LIMIT_SECONDS`          | `1800`       | Celery hard task limit                               |
| `COMPLIANCE_TASK_SOFT_TIME_LIMIT_SECONDS`     | `1500`       | Controlled timeout threshold                         |
| `COMPLIANCE_MAX_RETRIES`                      | `1`          | Transient compliance retry count                     |
| `SECTION_MATCH_MIN_CONFIDENCE`                | `0.80`       | Minimum accepted canonical-section confidence        |
| `SECTION_FUZZY_MATCH_THRESHOLD`               | `0.88`       | Minimum fuzzy Latin alias similarity                 |
| `SECTION_HEADING_MAX_CHARACTERS`              | `200`        | Heading-candidate length guard                       |
| `SECTION_ALIAS_REGEX_MAX_LENGTH`              | `500`        | Maximum stored alias-regex length                    |
| `SECTION_ALIAS_REGEX_TIMEOUT_MS`              | `100`        | Alias-regex execution budget                         |
| `TRANSLATION_GROUP_MAX_BLOCK_DISTANCE`        | `3`          | Maximum structural block separation                 |
| `TRANSLATION_GROUP_MAX_VERTICAL_GAP`          | `120`        | Maximum PDF vertical grouping gap                    |
| `TRANSLATION_GROUP_MIN_CONFIDENCE`            | `0.65`       | Minimum group confidence used by strict validation   |
| `FINDING_EXPORT_MAX_ROWS`                     | `200000`     | Maximum finding rows per export                      |
| `COMPLIANCE_EXPORT_MAX_ROWS`                  | `200000`     | Maximum compliance rows per export                   |
| `FINDING_BULK_ACTION_MAX_ITEMS`               | `100`        | Maximum atomic finding bulk-action size              |

Docker Compose honors `DATABASE_HOST` and `DATABASE_PORT`. Use `postgres` for
the bundled database or set an external hostname. `DATABASE_NAME`,
`DATABASE_USER`, and `DATABASE_PASSWORD` default to the corresponding
`POSTGRES_*` values, so the bundled and application targets can be separated
without changing the local PostgreSQL container.
`BACKEND_CORS_ORIGINS` can contain multiple comma-separated origins without
spaces.

## Running with Docker

After configuring `.env` and installing the local models, build and start the
Phase 8 stack:

```bash
docker compose up --build -d
docker compose ps
```

Apply the database migration and create the bootstrap administrator:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.create_admin
docker compose exec backend python -m scripts.seed_master_data
docker compose exec backend python scripts/seed_section_definitions.py
```

Useful URLs:

- Login: <http://localhost:5173/login>
- Frontend application: <http://localhost:5173>
- Master Data overview: <http://localhost:5173/master-data>
- Document Register: <http://localhost:5173/documents>
- Add Document: <http://localhost:5173/documents/new>
- Archived Documents: <http://localhost:5173/documents/archived>
- Single Upload: <http://localhost:5173/documents/upload>
- Batch Upload: <http://localhost:5173/documents/batch-upload>
- Upload History: <http://localhost:5173/documents/upload-history>
- Extraction Queue: <http://localhost:5173/documents/extraction-queue>
- Extraction History: <http://localhost:5173/documents/extraction-history>
- OCR Queue: <http://localhost:5173/documents/ocr-queue>
- OCR History: <http://localhost:5173/documents/ocr-history>
- Language Detection: <http://localhost:5173/documents/language-detection>
- Backend root: <http://localhost:8000>
- Health endpoint: <http://localhost:8000/api/v1/health>
- Dependency readiness: <http://localhost:8000/api/v1/health/dependencies>
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

Stop containers while retaining PostgreSQL data:

```bash
docker compose down
```

The `postgres_data` and `redis_data` volumes preserve database and broker data,
and the bind-mounted `storage` directory preserves application files.
PostgreSQL and Redis are intentionally reachable only inside the Compose
network. `docker compose down -v` permanently deletes the development data
volumes.

The workers are intentionally separate:

```bash
docker compose logs worker
docker compose logs worker-ocr
docker compose logs worker-language
docker compose logs worker-compliance
docker compose exec worker celery -A app.workers.celery_app inspect ping
docker compose exec worker-ocr celery -A app.workers.celery_app inspect ping
docker compose exec worker-language celery -A app.workers.celery_app inspect ping
docker compose exec worker-compliance celery -A app.workers.celery_app inspect ping
```

## Running local development

Copy and configure the root `.env` first. Start the backend from one terminal:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
python -m scripts.create_admin
python -m scripts.seed_master_data
python scripts/seed_section_definitions.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

This direct-run workflow expects PostgreSQL at the configured `DATABASE_HOST`
and `DATABASE_PORT`. Because relative paths follow the process working
directory, the default `STORAGE_ROOT=./storage` resolves to `backend/storage`
when these commands are run from `backend`. Set it to `../storage` if the
repository-root storage tree should also be used for direct host development.
Set `OCR_MODEL_ROOT=../models/ocr` and
`LANGUAGE_MODEL_PATH=../models/language/lid.176.bin` for host-run inference.
On macOS or Linux, activate the environment with:

```bash
source .venv/bin/activate
```

For host-run workers, start Redis and point `CELERY_BROKER_URL` and
`CELERY_RESULT_BACKEND` at that host (normally `localhost`). Start each queue
from another activated backend terminal:

```bash
celery -A app.workers.celery_app worker --loglevel=INFO --queues=extraction --concurrency=2 --hostname="extraction@%h"
celery -A app.workers.celery_app worker --loglevel=INFO --queues=ocr --concurrency=1 --hostname="ocr@%h"
celery -A app.workers.celery_app worker --loglevel=INFO --queues=language --concurrency=2 --hostname="language@%h"
celery -A app.workers.celery_app worker --loglevel=INFO --queues=compliance --concurrency=2 --hostname="compliance@%h"
```

The OCR worker is deliberately concurrency one because Paddle models and
300-DPI page images are memory intensive.

Run the frontend from another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to the backend during development. The production-style
frontend container uses nginx for the same proxy path.

## Database migration

Phase 2 creates authentication and authorization persistence. The Phase 3
migration adds `departments`, `sections`, `document_types`,
`document_statuses`, and `validation_rules`, then connects the existing
`users.department_id` field. The Phase 4 migration adds `documents` and
`document_revisions`, including the staged circular current-revision foreign
key, uniqueness constraints, lookup indexes, and Phase 4 audit actions. The
Phase 5 migration adds `document_files`, `upload_sessions`, and
`upload_session_items`, a partial unique index for one current primary file per
revision, file/upload enums, foreign keys, indexes, and Phase 5 audit actions.
The Phase 6 migration adds extraction jobs/runs, normalized containers,
blocks, tables and cells, `document_files.latest_extraction_run_id`, the active
job uniqueness constraint, search/order indexes, extraction enums, and audit
actions.
Phase 7 uses two migrations. `20260725_0006_phase7_ocr.py` adds OCR jobs,
runs, page results, blocks, OCR enums/audit actions, and
`document_files.latest_ocr_run_id`.
`20260725_0007_phase7_language_detection.py` adds language jobs, runs, block
results, container summaries, detector enums/audit actions, and
`document_files.latest_language_detection_run_id`. Active-job partial unique
indexes prevent duplicate OCR or language jobs for one file while retained
completed runs remain immutable history.
The Phase 8 migration,
`20260726_0008_phase8_compliance_foundation.py`, adds canonical section
profiles, definitions and aliases; compliance jobs and immutable runs;
detected sections and per-language results; translation groups and members;
validation findings and occurrences; the latest-compliance-run link; and the
required compliance/finding audit actions and indexes.
Apply all pending migrations from `backend`:

```bash
alembic upgrade head
alembic current
```

To roll back only Phase 8 while retaining Phase 7 OCR and language data:

```bash
alembic downgrade 20260725_0007
```

To roll back only Phase 7 while retaining Phase 6 extraction data:

```bash
alembic downgrade 20260725_0005
```

To roll back only Phase 6 while retaining Phase 5 physical-file data:

```bash
alembic downgrade 20260725_0004
```

To additionally roll back Phase 5 while retaining the Phase 4 Document Register:

```bash
alembic downgrade 20260725_0003
```

To additionally roll back Phase 4 while retaining Phase 3 Master Data:

```bash
alembic downgrade 20260725_0002
```

To additionally roll back Phase 3 while retaining Phase 2 authentication:

```bash
alembic downgrade 20260725_0001
```

With running containers:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

All future schema changes must use Alembic; do not create application tables by
hand.

Seed the idempotent Master Data defaults after migrating:

```bash
python -m scripts.seed_master_data
python scripts/seed_section_definitions.py
```

Both scripts create only missing defaults and do not replace custom
administrator data. `seed_section_definitions.py` creates the idempotent
`DEFAULT-3LANG` compliance profile, 12 canonical section definitions, and 46
Indonesian, English, and Simplified Chinese aliases, then links the default
validation rule.

Default seed content:

- Departments: `HRM`, `ICT`, `FNC`, `ENV`, `PRC`, `ACP`, `CHP`, `CCP`
- Document Types: `SOP`, `WIN`, `POL`, `GUI`, `MAN`, `FRM`, `PLN`
- Document Statuses: `DRAFT`, `UNDER_REVIEW`, `APPROVED`, `EFFECTIVE`,
  `OBSOLETE`, `SUPERSEDED`
- Validation Rule: `DEFAULT-3LANG` with Indonesian, English, and Chinese
  required at 95% minimum coverage, compliance score 95, and partial score 70

Organization-specific department sections remain unseeded; the Phase 8
canonical compliance section catalog is separate and is seeded by
`seed_section_definitions.py`.

## Seed administrator and default login

Set `DEFAULT_ADMIN_NAME`, `DEFAULT_ADMIN_EMAIL`, and
`DEFAULT_ADMIN_PASSWORD` in `.env`, then run:

```bash
python -m scripts.create_admin
```

Or with Docker:

```bash
docker compose exec backend python -m scripts.create_admin
```

The example login email is `admin@example.com`. There is intentionally no safe,
shared default password: the example password is only a visible placeholder and
must be replaced before seeding.

Treat the bootstrap account as privileged:

- Use a unique strong password.
- Never reuse the placeholder in any environment.
- Do not commit the real password.
- Rotate any credential that was exposed in terminal history, logs, or source
  control.

## Authentication API

Phase 1 health remains available:

```http
GET /api/v1/health
```

Phase 2 adds:

```http
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

FastAPI documents the request and response schemas at
<http://localhost:8000/docs>. Protected endpoints require the access token as a
Bearer credential.

## Master Data API

All Master Data endpoints use the `/api/v1/master-data` prefix and the existing
Phase 2 bearer authentication:

```text
GET    /overview

GET    /departments
POST   /departments
GET    /departments/options
GET    /departments/{id}
PUT    /departments/{id}
PATCH  /departments/{id}/activate
PATCH  /departments/{id}/deactivate

GET    /sections
POST   /sections
GET    /sections/options
GET    /sections/{id}
PUT    /sections/{id}
PATCH  /sections/{id}/activate
PATCH  /sections/{id}/deactivate

GET    /document-types
POST   /document-types
GET    /document-types/{id}
PUT    /document-types/{id}
PATCH  /document-types/{id}/activate
PATCH  /document-types/{id}/deactivate

GET    /document-statuses
POST   /document-statuses
GET    /document-statuses/{id}
PUT    /document-statuses/{id}
PATCH  /document-statuses/{id}/activate
PATCH  /document-statuses/{id}/deactivate

GET    /validation-rules
POST   /validation-rules
GET    /validation-rules/{id}
PUT    /validation-rules/{id}
PATCH  /validation-rules/{id}/activate
PATCH  /validation-rules/{id}/deactivate
PATCH  /validation-rules/{id}/set-default
```

List endpoints support server-side search, active-state filters, sorting, and
pagination. Section lists additionally support `departmentId`.

## Master Data XLSX import and export

Only `.xlsx` workbooks are accepted. Download a template for one of
`departments`, `sections`, `document-types`, `document-statuses`, or
`validation-rules`:

```http
GET /api/v1/master-data/import/template/{entityType}
```

Import uses two explicit multipart requests:

```http
POST /api/v1/master-data/import/preview
POST /api/v1/master-data/import/confirm
```

Preview validates headers and every row without persisting data. Confirm
requires the file again and revalidates it rather than trusting browser state.
`CREATE_ONLY` skips existing records; `UPSERT` updates them and requires update
permission. Invalid rows are reported and skipped while valid rows are
processed transactionally up to `MASTER_DATA_IMPORT_MAX_ROWS`.

Template columns:

| Entity            | Required workbook columns                                                                            |
| ----------------- | ---------------------------------------------------------------------------------------------------- |
| Departments       | `code`, `name`, `description`, `is_active`                                                           |
| Sections          | `department_code`, `code`, `name`, `description`, `is_active`                                        |
| Document Types    | `code`, `name`, `category`, `description`, `requires_section`, `is_active`                           |
| Document Statuses | `code`, `name`, `description`, `display_order`, `is_initial`, `is_final`, `is_obsolete`, `is_active` |
| Validation Rules  | Language, coverage, order, section, score, default, document-type, and active-state fields           |

Filtered export uses:

```http
GET /api/v1/master-data/export/{entityType}
```

Exported workbooks contain formatted headers, freeze panes, filters,
auto-sized columns, actual filtered data, and workbook export time. Results are
limited by `MASTER_DATA_EXPORT_MAX_ROWS`. Import and export are both audited.

## Master Data frontend

Authenticated users with `master_data:view` can open:

- `/master-data`
- `/master-data/departments`
- `/master-data/sections`
- `/master-data/document-types`
- `/master-data/document-statuses`
- `/master-data/validation-rules`

Lists use server-side search, filters, sorting, and pagination. Create, update,
activation, and deactivation controls are rendered only when the current
session has the matching permission, while the backend validates every action
again.

## Document and revision model

A `Document` is the stable register identity. A `DocumentRevision` stores each
version-specific status, validation rule, date, SharePoint URL, external
reference, and remarks. One document may have many revisions but at most one
current revision.

Default base-code formats:

```text
{company}-{department}-{section}-{documentType}-{number}
{company}-{department}-{documentType}-{number}          # section not required
```

For example:

```text
MTI-HRM-IER-SOP-001
MTI-HRM-POL-001
```

The full revision code is:

```text
{baseDocumentCode}_{revisionCode}
MTI-HRM-IER-SOP-001_Rev.000
```

Components are trimmed, normalized to uppercase, and validated before code
generation. A section is required only when the selected active Document Type
sets `requires_section=true`; when present it must be active and belong to the
selected department.

Revision input is normalized to the `Rev.` prefix. Numeric revisions are padded
to at least three digits, while alphabetic revisions are uppercase:

```text
0, 000, Rev000, rev.000 -> Rev.000
1, Rev.1                 -> Rev.001
12                       -> Rev.012
A, rev.a                 -> Rev.A
```

Changing a code component regenerates every full revision code in one
transaction. Once a revision is final/effective, only Super Admin or Document
Controller may make that sensitive change, and a change reason is required.

## Document Register API

All routes use the `/api/v1/documents` prefix:

```text
GET    /
POST   /
GET    /form-options
POST   /parse-code
GET    /export

GET    /import/template
POST   /import/preview
POST   /import/confirm

POST   /bulk/archive
POST   /bulk/restore
POST   /bulk/update-status

GET    /{documentId}
PUT    /{documentId}
POST   /{documentId}/archive
POST   /{documentId}/restore

GET    /{documentId}/revisions
POST   /{documentId}/revisions
GET    /{documentId}/revisions/{revisionId}
PUT    /{documentId}/revisions/{revisionId}
POST   /{documentId}/revisions/{revisionId}/set-current
POST   /{documentId}/revisions/{revisionId}/supersede
```

The list endpoint supports database pagination plus search, department,
section, document-type, current status, validation-rule, revision, company,
archive, SharePoint URL, creator, created-date, and effective-date filters.
Sorting is server-side. Users without `documents:view_all_departments` are
always constrained by `document.department_id == current_user.department_id`
for list, detail, update, revision history, archive/restore, and export.

`GET /form-options` returns active, department-scoped form choices with the
Document Type section requirement, initial status, and default-rule metadata.
This lets department users create documents without granting access to Master
Data administration pages.

Bulk archive, restore, and current-revision status update accept at most 100
document IDs and return an item-level success/failure result. Bulk operations
never hard-delete records or change document codes.

## Document Register XLSX import and export

Only `.xlsx` files within `DOCUMENT_IMPORT_MAX_FILE_SIZE_MB` are accepted. The
backend is authoritative for this configurable limit; the bundled frontend proxy
uses a separate 512 MB transport ceiling so it does not preempt normal backend
validation.
Preview parses and validates every row without persistence. Confirm requires
the workbook again and reruns all validation; it never trusts browser preview
state.

The `Document Register` sheet uses these columns:

```text
company_code
department_code
section_code
document_type_code
document_number
document_title
description
revision
document_status_code
validation_rule_code
issue_date
effective_date
review_date
expiry_date
owner_department_code
document_owner_name
sharepoint_url
external_reference
remarks
```

Company, department, document type, document number, title, and revision are
required. Section requirement comes from the Document Type. Blank status uses
the active initial status, while blank validation rule follows the Document
Type-specific and then global default resolution. The template includes a
second `Reference` sheet populated from active Master Data.

Confirm modes:

- `CREATE_ONLY` creates new identities and skips existing documents.
- `CREATE_AND_ADD_REVISION` creates new identities and adds nonduplicate
  revisions to existing identities.
- `UPSERT_METADATA` additionally updates existing document metadata but never
  overwrites an existing revision.

Rows are classified as `VALID_CREATE`, `VALID_ADD_REVISION`, `DUPLICATE`,
`INVALID`, or `WARNING`. Invalid and duplicate rows are reported and skipped.
Import is limited by `DOCUMENT_REGISTER_IMPORT_MAX_ROWS`.

Filtered export emits the accessible current register view with company,
department, section, type, identity, revision, status, validation rule, dates,
ownership, SharePoint/external metadata, archive state, and timestamps. It uses
formatted headers, freeze panes, filters, safe cell values, hyperlinks, and an
application-timezone generated timestamp. Export is limited by
`DOCUMENT_REGISTER_EXPORT_MAX_ROWS`; department scope cannot be bypassed with
query parameters.

## Document Register frontend

Authenticated users with `documents:view` can open:

- `/documents`
- `/documents/archived`
- `/documents/:documentId`
- `/documents/:documentId/revisions`

The create and edit routes are additionally permission protected:

- `/documents/new`
- `/documents/:documentId/edit`

Filters are stored in URL query parameters, search is debounced, and the
register includes responsive row actions and safe bulk actions. The create page
can identify metadata from a code or supported filename, generates the base and
full codes in real time, and uses React Hook Form plus Zod. Detail and revision
screens use live API data; archived records remain readable but are read-only
until restored.

## Physical document upload and identification

Phase 5 uses a two-stage workflow. The first request streams the file into the
temporary prefix, validates its metadata and bytes, calculates SHA-256, parses
the filename with the Phase 4 code parser, and returns a persisted preview
session. No `DocumentFile` is created at this stage. Confirmation rechecks
session ownership, expiry, permissions, department scope, target state,
duplicate policy, and the stored bytes before moving the object and committing
the database transaction.

Identification may propose:

- attach to an existing revision without a current file;
- add a new revision to an existing document;
- create a document and its initial revision;
- replace a current file, with a mandatory reason; or
- manual review/skip when the filename is incomplete or ambiguous.

The server reuses the Phase 4 document and revision services. Their normal API
behavior remains commit-on-success; the upload workflow uses their
backward-compatible transaction mode so document, revision, file metadata, and
audit records can be committed together. A failed database operation removes
the moved final object, while a failed move prevents the database commit.

Exact duplicates on the same revision are rejected. Matches elsewhere produce
a warning, with cross-department details withheld from users outside that
scope. One revision has at most one current primary physical file. Replacing a
file retains the former object and metadata as `REPLACED`.

## Private storage and lifecycle

`BaseStorage` separates document workflows from the configured provider.
Phase 5 supplies `LocalStorage`; object keys use normalized POSIX-style relative
paths with UUID components, and every filesystem operation proves that its
resolved target remains beneath `STORAGE_ROOT`. Absolute paths, drive paths,
traversal components, control characters, unsafe archive entries, and
colliding destinations are rejected.

The local layout is:

```text
storage/
  documents/
    originals/
    temporary/
    quarantine/
    deleted/
  logs/
```

These directories are bind-mounted into the backend container and ignored by
Git except for their placeholders. They are not copied into either runtime
image. Confirmed files are served only by authenticated, permission-checked
streaming endpoints; there is no public storage URL.

Delete is a soft-delete: metadata changes to `DELETED` and the object moves to
the deleted prefix. Restore is explicit and conflicts if another current file
exists unless an authorized caller deliberately replaces it. The previous
file is never silently restored. Invalid signature/OOXML security checks may
move an object to quarantine, but Phase 5 does not claim antivirus scanning.

## Physical file API

All routes are beneath `/api/v1`:

```text
POST /document-files/upload
POST /document-files/upload/{sessionId}/confirm
POST /document-files/upload/{sessionId}/cancel
POST /document-files/batch-upload
POST /document-files/batch-upload/{sessionId}/confirm

GET  /document-files/history
GET  /document-files/{fileId}
GET  /document-files/{fileId}/download
POST /document-files/{fileId}/replace
POST /document-files/{fileId}/delete
POST /document-files/{fileId}/restore

GET  /documents/{documentId}/files
GET  /documents/{documentId}/revisions/{revisionId}/files
GET  /documents/{documentId}/revisions/{revisionId}/download
```

Upload and management permissions are independent:
`documents:upload`, `documents:download`, `documents:replace_file`,
`documents:delete_file`, `documents:batch_upload`, and
`documents:view_file_history`. Backend guards and department scope remain
authoritative even when the frontend hides a control.

Downloads stream in configured chunks and return `Content-Type`,
`Content-Length`, safe `Content-Disposition`,
`X-Content-Type-Options: nosniff`,
`Content-Security-Policy: default-src 'none'`, and
`Cache-Control: private, no-store`. API schemas never expose `storage_key` or a
server filesystem path.

## Batch upload and temporary cleanup

Batch preview accepts at most `DOCUMENT_BATCH_MAX_FILES` and
`DOCUMENT_BATCH_MAX_TOTAL_SIZE_MB`. Each file is validated independently and
confirmation uses a transaction per item, so an invalid or failed item does
not erase successful items. The response reports committed, skipped, failed,
created-document, created-revision, attached-file, and replaced-file counts.

Upload sessions expire after `TEMP_FILE_RETENTION_HOURS`. Run the idempotent
cleanup manually, from cron, or from a scheduled task:

```bash
cd backend
python -m scripts.cleanup_temporary_uploads
```

With Compose:

```bash
docker compose exec backend python -m scripts.cleanup_temporary_uploads
```

The command locks and expires eligible sessions, removes their temporary
objects, leaves active sessions untouched, writes an audit summary, and is safe
to run repeatedly. Phase 5 intentionally does not add an in-process scheduler.

## Physical upload frontend

Permission-protected routes are:

- `/documents/upload`
- `/documents/batch-upload`
- `/documents/upload-history`
- `/documents/:documentId/revisions/:revisionId/file`

The single flow provides an accessible dropzone, client-side Zod validation,
Axios progress, identification preview, action/metadata correction, duplicate
warnings, expiry handling, and a final result. The batch page provides
per-file previews/actions and result filtering. Document detail and revision
views expose live file history, download, replace, delete, and restore controls
only for the relevant permissions.

## Supported file formats

Operational physical upload supports only:

- PDF (`.pdf`, `application/pdf`)
- DOCX (`.docx`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
- XLSX (`.xlsx`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)

Extension, declared MIME, and detected signature/structure must agree. PDF must
begin with `%PDF-`. DOCX and XLSX must be readable, non-encrypted OOXML ZIP
archives with their required content-type and document/workbook entries.
Archive entry count, aggregate expanded size, per-entry and aggregate
compression ratio, duplicate paths, traversal paths, symbolic links, and CRC
integrity are checked without extraction.

PPTX, legacy Office formats, images, mismatched extensions/MIME, fake PDFs,
corrupt OOXML, oversized files, and ZIP-bomb-like archives are rejected. The
frontend allowlist is only an early usability check; the backend performs every
authoritative validation.

## Document content extraction

The authenticated API creates a durable database job and sends only its UUID to
the dedicated Celery queue. The worker copies the private storage object into
an exact worker-owned temporary file, verifies its size and SHA-256 hash,
selects the extractor, reports progress at safe checkpoints, persists the
normalized result in one transaction, and removes the temporary file. Older
runs remain read-only history when re-extraction creates a new latest run.

Supported extraction behavior:

- PDF: page containers, selectable text blocks, page/block source references,
  and bounding boxes. Image-dominant pages are detected; a mostly scanned file
  becomes `OCR_REQUIRED`, while mixed selectable/scanned content becomes
  `PARTIALLY_COMPLETED`. The extraction worker itself does not perform OCR;
  Phase 7 consumes this retained scan assessment on the separate OCR queue.
- DOCX: body paragraphs and tables remain in source order; headings, table
  cells, merged spans, headers, and footers are retained. DOCX does not contain
  reliable rendered page numbers. Drawings, comments, embedded objects,
  tracked/complex controls, and similar content produce warnings rather than
  fabricated text.
- XLSX: worksheets, visibility and sheet metadata, non-empty cells, formulas,
  available cached-value metadata, and merged ranges are read without
  calculation. Formulas, macros, external links, and embedded executables are
  never run or fetched.

The unified model stores ordered containers, searchable blocks, structured
tables/cells, normalized text counts, source references, safe location
metadata, warnings, source hashes, and a deterministic content hash. Search is
case-insensitive plain-text matching backed by PostgreSQL GIN indexes across
normalized block text, source references, and container names; it returns
plain-text snippets, never database HTML. Container/table list responses omit
unbounded aggregate raw text, while the viewer assembles a paginated raw-text
preview from blocks. Full raw content remains available to authorized users in
streamed JSON/TXT exports, whose private temporary files are deleted afterward.

Extraction API:

```text
POST /api/v1/extractions
GET  /api/v1/extractions
GET  /api/v1/extractions/{jobId}
POST /api/v1/extractions/{jobId}/cancel
POST /api/v1/document-files/{fileId}/reextract
GET  /api/v1/document-files/{fileId}/extraction
GET  /api/v1/document-files/{fileId}/extraction-history
GET  /api/v1/extraction-runs/{runId}
GET  /api/v1/extraction-runs/{runId}/containers
GET  /api/v1/extraction-runs/{runId}/blocks
GET  /api/v1/extraction-runs/{runId}/tables
GET  /api/v1/extraction-runs/{runId}/search?q=document+control
GET  /api/v1/extraction-runs/{runId}/export?format=json
GET  /api/v1/extraction-runs/{runId}/export?format=txt
```

Frontend routes:

```text
/documents/extraction-queue
/documents/extraction-history
/documents/:documentId/extracted-content
/documents/:documentId/revisions/:revisionId/extracted-content
/documents/:documentId/revisions/:revisionId/extraction-history
```

Queue polling stops at `COMPLETED`, `PARTIALLY_COMPLETED`, `OCR_REQUIRED`,
`FAILED`, or `CANCELLED`. Cancellation is cooperative between PDF pages, DOCX
body units, and XLSX worksheets; it cannot interrupt a single library call
instantaneously.

Extraction remains department-scoped and permission-controlled. The API never
returns a storage key or filesystem path. OOXML inspection rejects DTD/entity
content, does not resolve external entities or relationships, and retains the
Phase 5 ZIP/security limits. Error responses use controlled codes and never
return a worker traceback.

## PDF OCR

OCR is local, PDF-only, and additive. It never replaces native selectable
text. The OCR worker copies the private PDF to a worker-owned temporary path,
selects eligible pages from the retained extraction result, renders one page
at a time with PyMuPDF, preprocesses a private PNG, invokes PaddleOCR, maps
polygons back to render coordinates, persists the result and provenance, then
removes every rendered/preprocessed artifact.

Profiles:

- `LATIN`: Indonesian and English recognition with
  `latin_PP-OCRv5_mobile_rec`
- `CHINESE_SIMPLIFIED`: Simplified Chinese recognition with
  `PP-OCRv5_mobile_rec`
- `AUTO_MULTILINGUAL`: Latin first, followed by one bounded Chinese pass because
  selecting this profile is an explicit multi-language OCR request; overlapping
  blocks are deduplicated without discarding provenance

`OCR_AUTO_MULTILINGUAL_CHINESE_PASS=false` guarantees a single Latin pass for
the automatic profile. When enabled, the automatic profile runs at most the two
documented passes. Confidence, character-count, Han-script, force, and validation
signals are retained in result metadata so the reason for the pass remains
auditable.

Both profiles use the local `PP-OCRv5_mobile_det` detector. Optional document
orientation uses the local `PP-LCNet_x1_0_doc_ori` model. The provider receives
explicit local directories and model names; it does not rely on an implicit
runtime download.

Paddle's detected `0`/`90`/`180`/`270` correction is retained as page
`rotationApplied` and block `orientation`. PDF page-rotation metadata remains
separate provenance (`sourceRotation`), is not added to the OCR correction, and
the source PDF is never modified.

Page selection includes pages identified as scanned by Phase 6, pages below
`OCR_SELECTABLE_TEXT_MIN_CHARACTERS`, valid manually selected pages, and
re-OCR pages. A page with sufficient native selectable text is skipped unless
an authorized explicit force request is used. OCR rejects DOCX, XLSX,
historical/replaced/deleted files, invalid page numbers, excessive page counts,
oversized renders, and unsupported profiles.

Preprocessing profiles:

- `NONE`: recognize the original bounded render
- `STANDARD`: grayscale, resize low-resolution input, contrast enhancement,
  median denoise, and bounded deskew
- `AGGRESSIVE`: stronger contrast/denoise/sharpen plus adaptive thresholding
  and morphology

Rendering defaults to 300 DPI and is bounded to 6000 x 6000 pixels. Block
confidence, page minimum/maximum/average confidence, rotation, deskew angle,
polygon, bounding box, model/profile, source page, content hashes, and safe
warnings are retained. A page becomes `LOW_CONFIDENCE` when the configured
proportion of blocks falls below `OCR_LOW_CONFIDENCE_THRESHOLD`; low-confidence
blocks are retained for review. Upscaled low-resolution input also retains the
explicit `OCR_LOW_RESOLUTION` warning.

OCR API:

```text
POST /api/v1/ocr/jobs
GET  /api/v1/ocr/jobs
GET  /api/v1/ocr/jobs/{jobId}
POST /api/v1/ocr/jobs/{jobId}/cancel
GET  /api/v1/ocr/runs/{runId}
GET  /api/v1/ocr/runs/{runId}/pages
GET  /api/v1/ocr/runs/{runId}/pages/{pageNumber}
GET  /api/v1/ocr/runs/{runId}/blocks
GET  /api/v1/ocr/runs/{runId}/export?format=json
GET  /api/v1/ocr/runs/{runId}/export?format=txt
POST /api/v1/ocr/runs/{runId}/reocr
GET  /api/v1/document-files/{fileId}/ocr
GET  /api/v1/document-files/{fileId}/ocr-history
```

Re-OCR requires an audit reason and creates a new immutable run; older results
are not deleted. A targeted run stores only its selected pages. The merged
viewer and downstream detector resolve a bounded, same-file/same-extraction
ancestry where the newest page result wins and unselected pages remain backed
by the earlier run without copying rows. Failed or cancelled runs cannot be
used as re-OCR ancestry. Synchronous duplicate-job responses expose
`OCR_ACTIVE_JOB_EXISTS`. Cancellation is cooperative between page and provider
checkpoints and cannot interrupt an individual native inference call
instantaneously.

## Hybrid language detection

Language detection reads only retained extracted/OCR text. It never opens
Office files, runs formulas/macros, follows relationships, translates content,
or sends content to a remote model. The worker builds a deterministic merged
snapshot: sufficient native PDF text wins for that page, OCR supplements
low/no-text pages, and duplicate provenance/content is counted once. DOCX and
XLSX use their native extracted blocks and are never OCR inputs.

The detector combines:

1. Unicode letter/script statistics, including Han and Latin character ratios
2. local fastText `lid.176` predictions
3. Indonesian function-word and affix signals
4. English function-word signals
5. eligibility rules for empty, numeric/punctuation-only, URL-only,
   email-only, code-like, and insufficient text
6. mixed-language composition rules

Stable codes are `id`, `en`, `zh`, `mixed`, `unknown`, and `other`.
`unknown` means the text is ineligible or evidence is below the configured
minimum; `other` means the model has positive evidence for a non-target
language. Han characters are counted without relying on whitespace. A Han
ratio of at least `0.20` creates a strong Mandarin candidate, but one Han
character does not force the whole block to Chinese.

Mixed classification requires two strong target-language signals. Indonesian
and English may use dual lexical evidence at the configured `0.25` secondary
threshold. Han/Latin mixtures require each script to reach the configured
`0.15` character ratio. The original composition scores and primary language
remain retained; a mixed result is not forced into one target language.

Coverage is explicitly preliminary:

- block coverage is each eligible language weight divided by all eligible
  block weight
- character coverage is each eligible language character weight divided by
  all eligible characters
- mixed blocks are distributed by trusted composition scores; otherwise they
  remain in the `mixed` category
- a target language is `PRESENT` only with at least two blocks and 20
  characters by default; short documents report `INSUFFICIENT_EVIDENCE`

No Phase 7 response labels a document compliant or evaluates translation
equivalence.

Language API:

```text
GET  /api/v1/language-detection/documents
POST /api/v1/language-detection/jobs
GET  /api/v1/language-detection/jobs
GET  /api/v1/language-detection/jobs/{jobId}
POST /api/v1/language-detection/jobs/{jobId}/cancel
GET  /api/v1/language-detection/runs/{runId}
GET  /api/v1/language-detection/runs/{runId}/blocks
GET  /api/v1/language-detection/runs/{runId}/containers
GET  /api/v1/language-detection/runs/{runId}/summary
GET  /api/v1/language-detection/runs/{runId}/export?format=json
GET  /api/v1/language-detection/runs/{runId}/export?format=xlsx
POST /api/v1/language-detection/runs/{runId}/redetect
GET  /api/v1/document-files/{fileId}/language-detection
GET  /api/v1/document-files/{fileId}/language-detection-history
```

JSON/XLSX exports are bounded, use sanitized filenames, prefix
formula-triggering spreadsheet text, remove XML-illegal control characters,
and remove their private temporary artifact after the response. Re-detection
requires an audit reason and retains older runs. Synchronous duplicate-job
responses expose `LANGUAGE_ACTIVE_JOB_EXISTS`.

## Phase 7 frontend

```text
/documents/ocr-queue
/documents/ocr-history
/documents/language-detection
/documents/:documentId/ocr-results
/documents/:documentId/language-results
/documents/:documentId/revisions/:revisionId/ocr-results
/documents/:documentId/revisions/:revisionId/language-results
```

The OCR UI shows progress, stage, profile, page summaries, confidence,
rotation, bounding boxes, history, safe cancel/re-OCR dialogs, filters, and
JSON/TXT export. The language inventory includes every current available file,
even before its first detection, and reports the latest extraction, OCR, and
language job states without deriving placeholder statuses. It starts detection
with the latest usable extraction/OCR source and exposes permission-gated view,
re-detect, and JSON/XLSX export actions. Result pages keep OCR confidence
separate from detector confidence, show language presence and the preliminary
disclaimer, report target-specific average confidence, paginate every retained
container beyond the first 500, and support block/source/confidence/search
filters and paginated history.
Document detail exposes actions only when the file type/state and permission
allow them; it never shows OCR for DOCX/XLSX.

## Phase 8 validation

Phase 8 evaluates retained extraction, OCR, and language-detection evidence. A
run stores the exact source identifiers, source-content hash, and immutable
validation-rule snapshot used to produce it. Validation never reads arbitrary
client paths and never mutates the source runs.

The default rule evaluates document-code validity, required-language presence,
language block/character coverage, required canonical sections, language
order, structural translation groups, and multilingual table completeness.
Required-section validation can additionally enforce optional per-language
block and character coverage inside each section through snapshotted
`validationOptions` (`validateSectionCoverage`, evaluation mode, confidence
floor, and default or canonical-section thresholds). Existing rules retain
their former presence-only section behavior until this option is enabled.
The default weights are `10/25/15/20/10/15/5` and must total 100. Major and
minor findings subtract configured penalties before the critical-finding cap
is applied. By default, a score of at least 95 with every required language
and no open critical finding is compliant; 70–94.99 is partially compliant,
and a lower score is non-compliant. Missing prerequisites produce
`NOT_EVALUATED`; unreliable extraction, OCR, unknown-language, or grouping
evidence can produce `NEEDS_REVIEW`.

Section matching uses one active alias profile, canonical section definitions,
and Indonesian, English, or Simplified Chinese aliases. It tries normalized
exact matching before bounded prefix, regex, contains, and fuzzy strategies,
then applies the configured confidence floor. User-provided regular
expressions have length and complexity guards and a bounded execution time.
The default `DEFAULT-3LANG` seed includes TITLE, PURPOSE, SCOPE, DEFINITION,
REFERENCE, RESPONSIBILITY, PROCEDURE, RECORDS, ATTACHMENT,
REVISION_HISTORY, APPROVAL, and DISTRIBUTION.

Translation grouping is structural, not semantic: PDF uses page/order and
bounded vertical proximity, DOCX uses paragraph/table structure, and XLSX
supports adjacent language columns or language rows. Low-confidence groups
remain review evidence and may be excluded from strict denominators. Phase 8
does not judge whether translations have equivalent meaning. A document with
no table evidence treats table validation as not applicable (`SKIPPED`) rather
than making the complete run `NOT_EVALUATED`.

Rule snapshots retain the code, name, version, configuration, and weights used
by the run. Run responses, exports, and reports prefer this snapshot metadata,
so a later Validation Rule rename does not rewrite retained history. Legacy
Phase 3 language, coverage, and score fields remain synchronized with their
Phase 8 counterparts according to the fields actually supplied by the client.

Detected-section, translation-group, and run-finding endpoints use bounded
`page`/`pageSize` queries with a maximum page size of 500. The frontend keeps
server-side pagination and requests only the visible result page, while
XLSX/JSON exports count first and read retained rows in configured batches.
Summary responses include per-language presence, block/character coverage,
configured thresholds, confidence, and finding counts.

Compliance tasks run on the dedicated `compliance` queue. PostgreSQL workers
hold a session advisory execution lease across transaction commits, combine
it with row-level job ownership checks, and release it automatically if the
worker connection is lost. This prevents concurrent duplicate execution while
still allowing Celery redelivery after a hard worker loss.

Finding workflow is retained and audited:

```text
OPEN/REOPENED -> IN_REVIEW -> RESOLVED | FALSE_POSITIVE | ACCEPTED_RISK
IN_REVIEW -> OPEN when more source evidence is required
RESOLVED/FALSE_POSITIVE/ACCEPTED_RISK -> REOPENED
```

Revalidation creates a new run. Matching system findings are linked through
`previous_finding_id` and retained occurrences; old findings are not silently
resolved when no longer reproduced. Manual findings are never deleted by
revalidation. Bulk assignment and review validate the complete de-duplicated
set, department scope, assignee, permissions, and every transition before
committing one atomic transaction; the configured server-side item limit is
authoritative.

Phase 8 frontend routes:

```text
/documents/validation-queue
/documents/validation-history
/documents/:documentId/compliance
/documents/:documentId/revisions/:revisionId/compliance
/compliance
/compliance/languages
/compliance/sections
/compliance/language-order
/compliance/findings
/compliance/findings/review
/compliance/findings/:findingId
/reports/compliance
/reports/findings
/master-data/section-definitions
```

Phase 8 API:

```text
POST /api/v1/compliance/jobs
GET  /api/v1/compliance/jobs
GET  /api/v1/compliance/jobs/{jobId}
POST /api/v1/compliance/jobs/{jobId}/cancel
GET  /api/v1/compliance/runs/{runId}
GET  /api/v1/compliance/runs/{runId}/summary
GET  /api/v1/compliance/runs/{runId}/score-breakdown
GET  /api/v1/compliance/runs/{runId}/sections
GET  /api/v1/compliance/runs/{runId}/translation-groups
GET  /api/v1/compliance/runs/{runId}/findings
GET  /api/v1/compliance/runs/{runId}/export
POST /api/v1/compliance/runs/{runId}/revalidate
GET  /api/v1/compliance/runs/{runId}/compare/{otherRunId}
GET  /api/v1/document-files/{fileId}/compliance
GET  /api/v1/document-files/{fileId}/compliance-history

GET  /api/v1/findings
POST /api/v1/findings/manual
POST /api/v1/findings/bulk-actions
GET  /api/v1/findings/{findingId}
PUT  /api/v1/findings/{findingId}
POST /api/v1/findings/{findingId}/review
POST /api/v1/findings/{findingId}/return-to-open
POST /api/v1/findings/{findingId}/resolve
POST /api/v1/findings/{findingId}/reopen
POST /api/v1/findings/{findingId}/false-positive
POST /api/v1/findings/{findingId}/accept-risk
POST /api/v1/findings/{findingId}/assign
GET  /api/v1/findings/export

GET/POST/PUT/PATCH /api/v1/master-data/section-alias-profiles
GET/POST/PUT/PATCH /api/v1/master-data/section-definitions
GET/POST/PUT/PATCH /api/v1/master-data/section-aliases
POST /api/v1/master-data/section-definitions/test-match
POST /api/v1/master-data/section-definitions/import/preview
POST /api/v1/master-data/section-definitions/import/confirm
GET  /api/v1/master-data/section-definitions/export

GET /api/v1/compliance/overview
GET /api/v1/reports/compliance
GET /api/v1/reports/findings
```

## Phase 9 translation quality, glossary, revisions, and reports

Phase 9 is version `0.9.0`. Its quality-intelligence pipeline consumes the
retained extraction, OCR, language, translation-group, compliance, and finding
evidence created by Phases 6–8. It never rereads evidence from a remote service,
does not modify a source binary, and does not create an automatic translation.
The complete operational reference, including every Phase 9 API endpoint, is
in [docs/phase9-quality-intelligence.md](docs/phase9-quality-intelligence.md).

### Translation-similarity architecture

The `similarity` worker resolves compatible Phase 8 translation groups, creates
the required Indonesian–English, Indonesian–Chinese, and English–Chinese
pairs, performs local embedding inference, applies deterministic consistency
checks, and persists pair, section, run, model, provenance, confidence, and
finding evidence. Embedding vectors remain in memory and are neither stored nor
returned.

The default local provider and model are:

```text
Provider: sentence_transformer
Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Device: cpu
Model root: /app/models/similarity
```

The public API does not expose the model path. The operational path under the
default model root is
`sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2`.

Default thresholds are:

| Category       | Threshold              |
| -------------- | ---------------------- |
| `HIGH`         | `>= 0.85`              |
| `ACCEPTABLE`   | `>= 0.72` and `< 0.85` |
| `NEEDS_REVIEW` | `>= 0.58` and `< 0.72` |
| `LOW`          | `< 0.58`               |
| critical-low evidence | `< 0.35`       |

Critical-low is additional evidence, not an automatic Critical finding.
Similarity is not legal evidence, and a high score cannot guarantee a correct
translation.

Similarity confidence is distinct from the cosine score. It weights
translation-group confidence (30%), mean language confidence (25%), shortest
text sufficiency (15%), chunk completeness (15%), and the minimum retained
extraction/OCR confidence (15%). Low-confidence evidence is surfaced for
review or left `NOT_EVALUATED`.

Long text is bounded to 12,000 characters, split near paragraph or sentence
boundaries into 1,500-character chunks with 150-character overlap, and capped
at 50 chunks by default. The worker records truncation/completeness and
averages chunk embeddings before comparison.

Alongside semantic similarity, local deterministic services compare numbers,
dates, measurements/units, document references, and length ratios. Negation
matching uses conservative Indonesian, English, and Chinese cues. Because
context and morphology can be ambiguous, a negation mismatch is only a review
signal.

### Glossary profiles and validation

Glossary profiles resolve from the most specific active scope to the least
specific: department plus document type, department, document type, then
global. A profile owns terms and their `id`, `en`, and `zh` translations,
variants, and audited exceptions.

Term types are `PREFERRED`, `REQUIRED`, `FORBIDDEN`, `REFERENCE`, and
`ABBREVIATION`. Variants describe synonyms, abbreviations, spelling, legacy,
and forbidden forms. Exceptions can allow a variant, ignore a term, allow a
missing translation, or allow a forbidden term at global, department,
document, revision, file, or section scope. Every exception requires a reason,
can expire, follows department scope, and is never silently hard deleted.

Matching supports exact, whole-word, case-sensitive, bounded inflection,
bounded regex, configured variants, and Chinese substring evidence. Regex
length/execution are capped. Chinese text is not assumed to have whitespace
word boundaries, so ambiguous short or overlapping terms remain reviewable.

Glossary XLSX import uses preview and confirmation with `Terms`,
`Translations`, and `Variants` sheets. Exact headers and a generated import
example are documented in the Phase 9 guide and
`sample-documents/glossary/chinese-terms.xlsx`. Scoped export supports XLSX
and JSON. Validation runs retain preferred/forbidden/missing/inconsistent
matches, exceptions, findings, history, and export evidence.

### Revision comparison

Two revisions of the same document are aligned using retained entity type,
source reference, canonical section and translation group, container identity,
normalized exact/fuzzy text, and position. The default fuzzy threshold is
`0.58`; low-confidence alignment remains visible.

Change types are `ADDED`, `REMOVED`, `MODIFIED`, `MOVED`, `UNCHANGED`, `SPLIT`,
and `MERGED`. Summaries compare language coverage/regression, compliance score
and status, translation similarity, sections/groups, and findings. Finding
comparison classifies new, no-longer-reproduced, repeated, severity changed,
workflow-state changed, or unchanged evidence. “No longer reproduced” is a
candidate outcome only; the comparison never resolves an existing finding or
changes either source revision. Export formats are bounded JSON, XLSX, and PDF.

### Advanced reporting and snapshots

Advanced reports cover compliance overview, finding analytics, translation
similarity, glossary compliance, revision changes, department performance,
document-type performance, validation-rule performance, language quality, and
processing performance.

Filters include date range, departments, sections, document type/status,
validation rules, compliance statuses, finding severity/status, language pair,
glossary profile, revision range, and archived state. The backend enforces
permission and department scope independently of frontend navigation.

The reporting worker generates bounded XLSX, JSON, or PDF artifacts in private
storage. Each authenticated `report_snapshot` captures filters, dataset hash,
format, size, generator, department scope, timestamps, and expiry. Retention is
30 days by default; delete is a soft lifecycle transition. Full document text
is disabled (`REPORT_INCLUDE_FULL_TEXT=false`) and report context uses bounded
snippets.

Daily, weekly, monthly, and conservatively validated five-field cron schedules
can be configured with an IANA timezone. Phase 9 exposes an audited manual
schedule-run endpoint that queues one snapshot per configured format. It does
not claim automatic email delivery.

### Quality-score strategy

`SEPARATE_QUALITY_SCORE` is the default. It preserves existing Phase 8
compliance scores and statuses. Translation quality is the similarity
percentage, while glossary quality accounts for forbidden, missing, and
inconsistent term evidence. If an administrator explicitly selects a combined
mode, validation rules default to a 25% translation-similarity weight and 15%
glossary-compliance weight; the remaining percentage is structural
compliance. Mode and weights are stored as an immutable configuration
snapshot. Missing required evidence yields `NOT_EVALUATED` instead of a
fabricated zero.

### Model setup and offline runtime

The API and workers never download a model during startup. Run the explicit
installer once from an environment that is authorized to reach the model
source:

```bash
cd backend
python scripts/download_similarity_model.py
```

When `SIMILARITY_MODEL_PATH` is unset during host execution, the installer
stores the model under `<repository>/models/similarity`. In Compose,
`SIMILARITY_MODEL_PATH=/app/models/similarity` preserves the same files through
the `./models:/app/models` mount.

Verify only local files, without network access:

```bash
cd backend
python scripts/download_similarity_model.py --offline-verify
```

Compose persists `./models` and mounts it read-only in runtime workers. If the
model is absent, similarity fails in a controlled way or remains
`NOT_EVALUATED`; it does not fall back to a cloud provider.

### Phase 9 workers

| Service             | Queue                 | Default concurrency | Soft/hard limit | Retries |
| ------------------- | --------------------- | ------------------- | --------------- | ------- |
| `worker-similarity` | `similarity`          | 1                   | 3300s / 3600s   | 1       |
| `worker-glossary`   | `glossary`            | 2                   | 3300s / 3600s   | 1       |
| `worker-revision`   | `revision-comparison` | 2                   | 3300s / 3600s   | 1       |
| `worker-reporting`  | `reporting`           | 1                   | 3300s / 3600s   | 1       |

Local worker commands:

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=INFO --queues=similarity --concurrency=1 --hostname=similarity@%h
celery -A app.workers.celery_app worker --loglevel=INFO --queues=glossary --concurrency=2 --hostname=glossary@%h
celery -A app.workers.celery_app worker --loglevel=INFO --queues=revision-comparison --concurrency=2 --hostname=revision@%h
celery -A app.workers.celery_app worker --loglevel=INFO --queues=reporting --concurrency=1 --hostname=reporting@%h
```

The Phase 9 environment block in `.env.example` configures queue names,
concurrency, provider/model/device, batch and sequence limits, similarity
thresholds, text/chunk limits, regex safety, import/block/change/export limits,
snapshot retention, retry behavior, and soft/hard time limits. Important
defaults include:

```text
SIMILARITY_DB_BATCH_SIZE=500
GLOSSARY_IMPORT_MAX_ROWS=100000
GLOSSARY_VALIDATION_MAX_BLOCKS=2000000
GLOSSARY_DB_BATCH_SIZE=1000
REVISION_COMPARISON_MAX_BLOCKS=3000000
REVISION_COMPARISON_MAX_CHANGES=1000000
REVISION_COMPARISON_DB_BATCH_SIZE=1000
REPORT_EXPORT_MAX_ROWS=500000
REPORT_SNAPSHOT_RETENTION_DAYS=30
REPORT_PDF_MAX_TABLE_ROWS=5000
REPORT_XLSX_MAX_ROWS_PER_SHEET=1000000
REPORT_TEXT_SNIPPET_MAX_CHARACTERS=500
REPORT_INCLUDE_FULL_TEXT=false
```

### Phase 9 migration, routes, and tests

Revision `20260726_0009` follows `20260726_0008` and creates 16 similarity,
glossary, revision-comparison, and reporting tables. It also adds latest
similarity/glossary references to document files, source-run references to
validation findings, and quality-score mode/weights to validation rules.

```bash
cd backend
alembic upgrade head
alembic downgrade 20260726_0008
```

Phase 9 API groups are:

```text
/api/v1/similarity/jobs
/api/v1/similarity/runs
/api/v1/glossary/profiles
/api/v1/glossary/terms
/api/v1/glossary/exceptions
/api/v1/glossary/import
/api/v1/glossary/validation
/api/v1/revision-comparisons
/api/v1/reports/jobs
/api/v1/reports/snapshots
/api/v1/reports/schedules
```

Frontend routes are:

```text
/documents/similarity-queue
/documents/similarity-history
/documents/revision-comparison
/compliance/translation-similarity
/compliance/glossary
/master-data/glossary
/reports/translation-similarity
/reports/glossary-compliance
/reports/revision-changes
/reports/advanced-analytics
```

Generate and verify the exact synthetic fixture inventory:

```bash
cd backend
python scripts/generate_phase9_sample_documents.py
python -m pytest app/tests/test_phase9_sample_documents.py
```

The generator creates deterministic DOCX/XLSX examples under
`sample-documents/similarity`, `sample-documents/glossary`, and
`sample-documents/revisions`. They contain only synthetic test content.

### Phase 9 limitations and troubleshooting

- Similarity is not proof of legal or linguistic correctness; low similarity
  is not automatically Critical.
- The system does not translate, edit source files, or use cloud AI.
- Scheduled email delivery and SharePoint synchronization are unavailable.
- A missing model requires the explicit installer and offline verification;
  startup never downloads it.
- For worker memory pressure, retain low similarity/reporting concurrency and
  lower batch/row/block limits before scaling vertically.
- A low score on short text should be reviewed with text eligibility, group
  confidence, language confidence, and chunk completeness.
- For a missed glossary term, inspect profile scope, active state, language,
  preferred/forbidden flags, case/whole-word rules, and variants.
- Chinese boundary issues require explicit terms/variants; whitespace word
  boundaries are not reliable.
- Low revision alignment confidence should be investigated through section,
  entity type, source reference, normalized text, and position evidence.
- A failed PDF report should be checked against ReportLab/font availability
  and PDF row limits.
- An expired snapshot must be regenerated; private expired files are not
  downloaded.
- A queued job requires Redis plus the exact dedicated worker queue; inspect
  worker health and dispatch logs before rerunning.

## Quality checks

Backend:

```bash
cd backend
python -m ruff check app alembic scripts
python -W error -m pytest
python -m compileall -q app alembic scripts
python scripts/generate_phase7_sample_documents.py
python scripts/generate_phase8_sample_documents.py
python scripts/generate_phase9_sample_documents.py
python scripts/seed_section_definitions.py
```

Frontend:

```bash
cd frontend
npm run format:check
npm run lint
npm run test
npm run build
```

Compose:

```bash
docker compose --env-file .env.example config
docker compose ps
docker compose exec worker celery -A app.workers.celery_app inspect ping
docker compose exec worker-ocr celery -A app.workers.celery_app inspect ping
docker compose exec worker-language celery -A app.workers.celery_app inspect ping
docker compose exec worker-compliance celery -A app.workers.celery_app inspect ping
docker compose exec worker-similarity celery -A app.workers.celery_app inspect ping
docker compose exec worker-glossary celery -A app.workers.celery_app inspect ping
docker compose exec worker-revision celery -A app.workers.celery_app inspect ping
docker compose exec worker-reporting celery -A app.workers.celery_app inspect ping
curl http://localhost:8000/api/v1/health/dependencies
```

## Operational limitations

- Confirmation persists the session transition, each selected file, and the
  final session summary in separate transactions. An infrastructure crash
  after a file commit but before finalization can leave a valid file attached
  while the upload session still reports `UPLOADING`; there is no automatic
  session-finalization reconciler yet.
- Preview rollback performs a best-effort storage delete. If both the database
  write and that compensating delete fail, the object has no persisted retry
  marker; provider inventory/orphan scanning is deferred.
- Duplicate detection is rechecked at confirmation, but concurrent confirms
  for a previously unseen hash on different documents are not serialized with
  a database advisory lock.
- The restore UI does not yet offer the backend's explicit
  `replaceCurrent=true` conflict path, and the Uploaded By filter is populated
  from uploaders visible on the current history result page.
- The database has separate document and revision foreign keys. Their
  cross-field consistency is enforced by locked service validation rather than
  a composite database constraint.
- The bundled nginx limit is 550 MB. Keep it aligned if backend batch limits
  are raised, and ensure the container user can write the storage bind mount on
  Linux deployments.
- A process crash in the narrow interval after an extraction or compliance job
  commits but before its Celery dispatch can leave a durable `QUEUED` row
  without a queued message. An outbox/reconciliation process is not yet
  included.
- The Validation Rule API and typed response expose all Phase 8 configuration,
  but the existing administrator form still edits the legacy subset plus the
  complete 12-code required-section selector. Configure advanced weights,
  penalties, confidence thresholds, and section-coverage options through the
  authorized API until a dedicated advanced form is added.
- PDF multi-column reading order and PDF table recognition are best-effort;
  low-confidence tables remain text blocks.
- Container/table list responses omit unbounded aggregate raw text. Table
  responses cap inline cell details and indicate truncation in metadata; large
  content and raw-text previews use server-side block/container pagination or
  an authorized export within the configured limit.
- OCR is PDF-only. DOCX/XLSX remain native-extraction inputs, and PPTX/images
  are outside the supported document formats.
- OCR accuracy depends on scan quality, language profile, page geometry, and
  installed local models. Low confidence is retained and surfaced; it is not
  presented as a successful high-confidence transcription.
- Local PaddleOCR inference can be slow and memory intensive. Keep the OCR
  worker at low concurrency and capacity-test page/DPI limits before raising
  them.
- Language detection is block-level evidence, not translation-equivalence or
  semantic validation. Very short/technical content may remain `unknown`;
  presence and coverage are preliminary.
- Manual language override is not enabled, so the UI does not show a
  nonfunctional review control.
- Structural grouping does not establish semantic translation equivalence.
  Phase 9 similarity adds a confidence-aware review signal and glossary
  enforcement adds configured terminology checks, but neither proves a legally
  or linguistically correct translation. Automatic translation, cloud OCR,
  scheduled email delivery, and SharePoint synchronization remain deferred.

## Troubleshooting

**Compose rejects a required variable.** Copy `.env.example` to `.env` and
replace the database, JWT, and admin-password placeholders. Do not put real
secrets in `.env.example`.

**Login says the credentials are invalid.** Confirm the migration and seed
commands completed, use `DEFAULT_ADMIN_EMAIL`, and ensure the password matches
the value used when the account was seeded.

**The account is locked.** Wait `ACCOUNT_LOCK_MINUTES` before retrying. Repeated
failed attempts lock an account after `MAX_LOGIN_ATTEMPTS`; avoid automated
retry loops with bad credentials.

**A previously valid token is rejected.** The access token may have expired.
The frontend should refresh it once. If refresh also fails, log in again.
Changing `JWT_SECRET_KEY` invalidates all tokens signed with the former key.

**The browser reports a CORS error.** Add the exact frontend origin to
`BACKEND_CORS_ORIGINS`. Origin matching includes protocol and port. Recreate the
backend container after changing Compose environment values.

**The backend is unhealthy.** Open the health URL directly, run
`docker compose ps`, and inspect `docker compose logs backend`. The health probe
uses `API_V1_PREFIX`, so keep the frontend API base path aligned with it.

**The backend cannot connect to PostgreSQL.** Use `DATABASE_HOST=postgres` for
the bundled Compose database, `DATABASE_HOST=localhost` for a backend process
running directly on the host, or the actual hostname for an external database.
Confirm `DATABASE_NAME`, `DATABASE_USER`, and the selected password, then check
`docker compose logs backend`.

**The worker cannot connect to Redis.** In Compose, use the service hostname
`redis`; for a host-run worker, normally use `localhost`. Check
`docker compose logs redis worker`, confirm both Celery URLs, and verify
`redis-cli ping` or the Redis health status.

**An extraction stays `QUEUED`.** Confirm the worker is healthy and consumes
the configured `EXTRACTION_QUEUE_NAME`:

```bash
docker compose exec worker celery -A app.workers.celery_app inspect ping
docker compose logs worker
```

If Redis or the worker was unavailable during dispatch, retry from the UI after
the failed job is terminal. A crash in the documented post-commit/pre-dispatch
window requires an administrator to reconcile the stale job.

**A PDF reports `OCR_REQUIRED`.** The PDF has insufficient selectable text on
most pages. Queue Phase 7 OCR from the current PDF file, choose the appropriate
language/preprocessing profile, and monitor the OCR queue.

**An OCR, language, or compliance job stays `QUEUED`.** Confirm Redis and the
dedicated worker are healthy, inspect `worker-ocr`, `worker-language`, or
`worker-compliance` logs, and verify that the worker consumes the same queue
name configured on the API. The dependency-readiness endpoint reports all
workers independently.

**A compliance run is `NOT_EVALUATED`.** Inspect its prerequisite summary.
The latest compatible extraction and language-detection runs must exist; a
scan that requires OCR also needs a compatible completed OCR run. Queue the
missing prerequisite first instead of forcing a score from incomplete
evidence.

**A section heading is not matched.** Verify the active alias profile,
language, alias match type, confidence threshold, and definition state. Use
the test-match endpoint before changing production aliases. A rejected regex
must be simplified to satisfy the configured length, safety, and execution
limits.

**A finding action is rejected.** Check the finding's current state and your
atomic permission. Terminal findings can only be reopened; auditors and
viewers are read-only, and department scope is enforced by the backend.

**The OCR model cannot be loaded.** Run
`backend/scripts/download_ocr_models.py`, verify that the four Latin/Chinese
detection/recognition directories contain nonempty inference files, and check
the `/app/models` bind mount inside `worker-ocr`. The worker does not perform an
implicit production download.

**The Chinese profile is unavailable.** Verify the
`chinese_simplified/detection` and `chinese_simplified/recognition` directories
and rerun the model setup script. Do not substitute a remote OCR endpoint.

**The language model is missing.** Run
`backend/scripts/download_language_model.py`, verify the optional checksum and
the mounted `lid.176.bin`, then recreate `worker-language`. The model is loaded
lazily once per worker child, not once per request.

**The OCR worker runs out of memory or is too slow.** Keep concurrency at one,
reduce selected pages/DPI/dimensions, process large documents in bounded page
sets, and review the container memory limit. `AUTO_MULTILINGUAL` may run two
recognition passes.

**OCR confidence is low.** Inspect the original scan and page profile, try
`STANDARD` or `AGGRESSIVE` preprocessing, and use the explicit Chinese profile
where appropriate. Low-confidence text remains visible and is never silently
discarded.

**A PDF does not need OCR.** Pages with at least the configured selectable-text
threshold are deliberately skipped. Read the native extraction result or use a
valid explicit page/force request only when reprocessing is justified.

**An XLSX is rejected as too large.** Reduce its worksheets, used row bounds,
non-empty cells, or formulas, or deliberately adjust the corresponding
`XLSX_MAX_*` setting after capacity testing. Sparse sheets with extreme used
ranges are rejected to avoid excessive resource use.

**A DOCX completes with warnings.** Inspect the warning list for drawings,
comments, embedded objects, external relationships, or complex controls.
External resources and executables are intentionally not followed or run.

**The PostgreSQL password changed after first startup.** The official image
uses `POSTGRES_PASSWORD` only while initializing a new data directory. Rotate
the database role password or, only when development data may be discarded,
run `docker compose down -v` and recreate the stack.

**A migration fails or an authentication table is missing.** Confirm PostgreSQL
is healthy, then run `alembic current` and `alembic upgrade head` from
`backend`.

**A Master Data code is rejected as duplicate.** Codes are trimmed,
uppercased, and unique according to their entity. Section codes are unique
within one department. Search inactive records before choosing a new code;
deactivation does not release uniqueness.

**An XLSX import is rejected.** Start from the downloadable template, retain
the exact header names, use a real `.xlsx` workbook, and keep the row count
within `MASTER_DATA_IMPORT_MAX_ROWS`. Preview errors identify the row and field.
Use `UPSERT` only when existing records are intentionally being updated.

**Changes are not reflected in containers.** Rebuild the affected services:

```bash
docker compose up --build -d frontend backend worker worker-ocr worker-language worker-compliance worker-similarity worker-glossary worker-revision worker-reporting
```

Phase 9 is complete only when the Phase 1–8 regression suite, migration chain
and idempotent seeds, health and authentication checks, Master Data, Document
Register and physical-file workflows, extraction/OCR/language/compliance
workers, local model verification, all three language pairs, deterministic
consistency checks, glossary CRUD/import/export/validation/exceptions, revision
changes and comparisons, private advanced XLSX/JSON/PDF snapshots, schedule
manual run, frontend lint/tests/build, and Docker smoke checks all pass.
Automatic translation, source editing, and cloud AI remain intentionally
outside that historical Phase 9 milestone.

## Phase 10 SharePoint, notifications, and production hardening

Phase 10 is version `1.0.0`. Microsoft Graph is backend-only and disabled by
default; the application continues to operate with private Local Storage.

```text
Document -> Revision -> DocumentFile -> Storage Provider
                                      |- LOCAL
                                      |- SHAREPOINT
                                      `- HYBRID

Application Event -> Rule -> Recipient -> Safe Template -> Delivery
                                                    |- IN_APP
                                                    |- EMAIL_GRAPH
                                                    |- TEAMS
                                                    `- TELEGRAM
```

### Microsoft Entra ID and Graph

The backend uses MSAL confidential-client credentials with
`https://graph.microsoft.com/.default`. Development supports a client secret;
production should use a certificate. Access tokens are held only in a bounded
cache and are never persisted, logged, or returned to the frontend.

Use `Sites.Selected` and grant the application access only to the controlled
site. `Mail.Send` is separate and needed only when Graph email is enabled.
Broader `Files.ReadWrite.All` or `Sites.ReadWrite.All` permissions are
development fallbacks that require explicit risk review and admin consent.

Graph calls pass through one request service that adds a correlation ID, maps
safe errors, follows pagination, applies per-connection rate control, and
retries only transient `429`, `500`, `502`, `503`, `504`, timeout, and
temporary DNS failures. `Retry-After` takes precedence over exponential
backoff with jitter.

See [SharePoint setup](docs/sharepoint-setup.md) and
[Graph permissions](docs/microsoft-graph-permissions.md).

### SharePoint connections, mappings, and storage

Connections contain non-secret tenant/site/drive/library/root references.
Site resolution supports hostname/path or a pre-resolved site ID; drive
resolution selects the configured document library. Folder mapping resolution
is deterministic from section/document-type/department combinations down to a
global fallback. Metadata uses SharePoint internal column names and registered
typed transformers—never arbitrary configured code.

The SharePoint storage provider supports folder creation, direct upload up to
the configured threshold, sequential resumable upload sessions for large
files, authenticated streaming download, metadata, copy, move, rename,
application soft-delete/restore through reversible move operations, child
listing, and remote versions. Provider-native SharePoint Online recycle-bin
restore is not available for work/school drives through production Graph v1.0,
so `supports_restore` remains false and no `/beta` endpoint is used. A Graph
`DELETE` moves an item to the Microsoft 365 recycle bin and is not described as
verified physical purge. Temporary Graph download URLs remain server-side and
are never stored as permanent URLs. The five generated samples under
`sample-documents/sharepoint` contain no company data.

### Full, delta, webhook, and conflict synchronisation

Profiles support `OUTBOUND`, `INBOUND`, and `BIDIRECTIONAL`. Bidirectional
profiles require a conflict policy; the default is `MANUAL`. Remote deletes
follow one explicit soft-delete/archive/mark/ignore policy and never erase
document or revision history.

Full sync reconciles the configured scope. Incremental sync follows Graph delta
pagination and persists the new encrypted delta link only after successful
policy-compliant processing. Invalid delta state queues controlled
reconciliation. Webhook validation returns the Graph validation token as plain
text; normal events validate hashed client state, deduplicate, persist, and
queue work without performing synchronisation in the request.

Conflicts retain local/remote evidence and support `KEEP_LOCAL`, `KEEP_REMOTE`,
`KEEP_BOTH`, `MERGE_METADATA`, and explicit ignore decisions. A mandatory
comment and optimistic recheck precede resolution. See
[sync design](docs/sharepoint-sync-design.md) and
[conflict resolution](docs/sharepoint-conflict-resolution.md).

### Notifications

Rules cover document processing, findings, SharePoint sync/conflicts,
subscription renewal, reports, backups, workers, storage, and security events.
Templates are channel/language/version aware and rendered with controlled
variables. Recipient resolution uses trusted users, roles, departments, and
configured endpoints—not arbitrary event input.

In-app notifications expose unread count, mark-read/read-all, expiry, and safe
internal action routes. Graph email uses a fixed sender. Teams and Telegram
adapters are optional and disabled by default. Quiet hours, timezone, digest,
and per-channel preferences are retained. Remote failures use bounded retry
and delivery history without rolling back completed business transactions.
See [notification operations](docs/notifications.md).

### Security, observability, and retention

- Environment and optional Azure Key Vault secret providers
- AES-256-GCM versioned encryption for delta/client-state integration data
- Redis-backed rate limits on login, uploads, exports, Graph tests, manual sync,
  webhooks, and notification tests
- Explicit production CORS, trusted hosts/proxies, HTTPS, CSP, HSTS, and other
  security headers
- Bounded request IDs propagated to Celery and Graph
- JSON structured logs with recursive secret and document-content redaction
- Prometheus-compatible HTTP/DB/Redis/Celery/Graph/sync/notification metrics
  without high-cardinality document/user labels
- Configurable OpenTelemetry spans without document text
- `/health/live`, `/health/ready`, dependency health, cached worker heartbeat,
  and an authenticated System Health page
- Database-pool, Redis, Celery late-ack/prefetch/time-limit, idempotency,
  graceful shutdown, and dead-letter controls
- Optional ClamAV abstraction with production fail-closed quarantine
- Dry-run/batched retention with legal hold and audit summaries

Details are in [security hardening](docs/security-hardening.md),
[retention policy](docs/retention-policy.md), and
[monitoring and alerting](docs/monitoring-and-alerting.md).

### Production deployment

Create a protected `.env.production` from `.env.production.example`, provide
CA-issued TLS material and runtime secrets, then:

```bash
docker compose --env-file .env.production \
  -f docker-compose.production.yml build
docker compose --env-file .env.production \
  -f docker-compose.production.yml run --rm migrate
docker compose --env-file .env.production \
  -f docker-compose.production.yml up -d
```

The production topology uses Gunicorn/Uvicorn, Nginx static frontend and HTTPS
edge, eleven isolated Celery queues, Celery Beat, internal-only PostgreSQL and
Redis, persistent storage/model volumes, non-root application images,
read-only roots where practical, health checks, and optional ClamAV. Run only
one migration process. See [production deployment](docs/production-deployment.md)
and the [operational runbook](docs/operational-runbook.md).

### Backup and disaster recovery

`scripts/backup_postgres.sh` creates a custom-format database backup plus
SHA-256 sidecar. `scripts/restore_postgres.sh` refuses an unsafe production
target and verifies restore into an isolated database. Storage manifests are
checked with `scripts/verify_storage_hashes.py`; configuration snapshots are
recursively redacted.

SharePoint does not replace database or private-storage backup. RPO and RTO are
explicit stakeholder decisions and are intentionally not invented here. See
[backup and restore](docs/backup-and-restore.md) and
[disaster recovery](docs/disaster-recovery.md).

### CI, performance, and known limitations

The example GitHub workflows run backend/frontend lint, typing, tests,
migration checks, dependency audits, Bandit, npm audit, secret scanning,
container builds, and Trivy scans. `performance/phase10-load.js` provides a
rate-aware k6 scenario and does not aggressively load Microsoft Graph.
Run it against a fully started stack with:

```bash
BASE_URL=http://localhost:8000 k6 run performance/phase10-load.js
```

The default probe is `/health/ready`. For an isolated API smoke run where
workers are intentionally absent, set `HEALTH_PATH=/health/live`; do not use
that override as a production-readiness substitute.

Automated Graph, SharePoint, email, Teams, and Telegram integration tests use
mock transports by default. A real Microsoft 365 development tenant,
`Sites.Selected` grant/admin consent, production certificate, public DNS/TLS,
and organization-approved RPO/RTO remain deployment responsibilities. Phase 10
uses reversible move operations for application soft-delete/restore; native
SharePoint Online recycle-bin restore remains unavailable through production
Graph v1.0 for work/school drives. It does not add PPTX, automatic translation,
source editing, cloud LLMs, public file URLs, SharePoint page editing, broad
permission administration, digital signatures, Google Drive, Dropbox, or
OneDrive Personal integration.
