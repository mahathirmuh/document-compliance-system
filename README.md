# Document Compliance & Multilingual Validation System

Version 0.4.0 completes Phase 4 of the foundation for a Document Control
application that registers document metadata and revisions and will later
validate Indonesian, English, and Mandarin content. It is intentionally not a
full Document Management System.

Phase 1 established the React, FastAPI, async SQLAlchemy, Alembic, PostgreSQL,
and Docker foundation. Phase 2 added authentication, authorization, and the
protected application shell. Phase 3 added audited Master Data management and
XLSX import/export. Phase 4 adds the department-scoped Document Register,
revision history, archive/restore, and audited register import/export.

## Phase 4 scope

Implemented in this phase:

- Separate Document identity and Document Revision persistence
- Automatic base/full document-code generation and revision normalization
- PDF, DOCX, and XLSX filename metadata parsing without uploading the file
- Department-scoped list, detail, create, update, search, filters, sorting, and
  pagination
- Transactional revision creation, current-revision selection, and superseding
- Archive and restore without hard deletion
- Permission-aware bulk archive, restore, and current-revision status updates
- XLSX template, validation preview, confirmed register import, and filtered
  export
- SharePoint URL metadata without Microsoft Graph synchronization
- Audit records for document, revision, import/export, and bulk operations

All Phase 1 health, Phase 2 authentication, and Phase 3 Master Data behavior
remains available. Physical document upload, content extraction, OCR, language
detection/validation, findings, preview, processing queues, full review and
approval workflows, and SharePoint API synchronization remain intentionally
unimplemented.

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
  |-- Document Register and Revision services
  |-- Endpoint -> Service -> Repository -> Database
  |
  v
PostgreSQL 16 (internal container port 5432)

FastAPI ----> ./storage (persistent bind mount)
```

The frontend may hide navigation by role, but this is only a usability layer.
The backend remains the source of truth for every protected operation.

Phase 4 stores document and revision metadata in PostgreSQL. It does not accept
or store operational document binaries.

## Technology stack

| Layer       | Technology                                                                          |
| ----------- | ----------------------------------------------------------------------------------- |
| Frontend    | React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Zustand, Axios |
| Backend     | Python 3.12, FastAPI, Pydantic, JWT authentication                                  |
| Data access | SQLAlchemy 2.0 async, asyncpg, Alembic                                              |
| Database    | PostgreSQL 16                                                                       |
| Development | Docker, Docker Compose, ESLint, Prettier, Vitest, Pytest                            |

Document extraction libraries and the remaining product libraries are added in
the phases where their workflows are implemented.

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

## Environment configuration

| Variable                            | Example/default              | Purpose                                            |
| ----------------------------------- | ---------------------------- | -------------------------------------------------- |
| `APP_NAME`                          | `Document Compliance API`    | Backend service name                               |
| `APP_VERSION`                       | `0.4.0`                      | Backend version                                    |
| `VITE_APP_VERSION`                  | `0.4.0`                      | Frontend version                                   |
| `APP_ENV`                           | `development`                | Backend runtime environment                        |
| `APP_TIMEZONE`                      | `Asia/Makassar`              | IANA timezone used for export timestamps           |
| `BACKEND_DEBUG`                     | `false`                      | Backend debug mode                                 |
| `API_V1_PREFIX`                     | `/api/v1`                    | Versioned API prefix                               |
| `FRONTEND_PORT`                     | `5173`                       | Frontend host port                                 |
| `BACKEND_PORT`                      | `8000`                       | Backend host port                                  |
| `VITE_API_BASE_URL`                 | `/api/v1`                    | Browser-facing API base path                       |
| `VITE_API_URL`                      | `/api/v1`                    | Phase 2 API URL; falls back to `VITE_API_BASE_URL` |
| `VITE_DEV_API_PROXY_TARGET`         | `http://localhost:8000`      | Local Vite proxy target                            |
| `POSTGRES_DB`                       | `document_compliance`        | PostgreSQL database                                |
| `POSTGRES_USER`                     | `document_compliance`        | PostgreSQL user                                    |
| `POSTGRES_PASSWORD`                 | replace-required placeholder | Database password                                  |
| `DATABASE_HOST`                     | `localhost`                  | Host-run PostgreSQL hostname                       |
| `DATABASE_PORT`                     | `5432`                       | PostgreSQL connection port                         |
| `DATABASE_ECHO`                     | `false`                      | SQLAlchemy SQL logging                             |
| `BACKEND_CORS_ORIGINS`              | `http://localhost:5173`      | Comma-separated allowed origins                    |
| `JWT_SECRET_KEY`                    | replace-required placeholder | JWT signing secret; at least 32 random characters  |
| `JWT_ALGORITHM`                     | `HS256`                      | JWT signing algorithm                              |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`   | `15`                         | Access-token lifetime                              |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS`     | `7`                          | Refresh-token lifetime                             |
| `MAX_LOGIN_ATTEMPTS`                | `5`                          | Failed attempts before temporary lock              |
| `ACCOUNT_LOCK_MINUTES`              | `15`                         | Temporary lock duration                            |
| `DEFAULT_ADMIN_NAME`                | `System Administrator`       | Seeded administrator name                          |
| `DEFAULT_ADMIN_EMAIL`               | `admin@example.com`          | Seeded administrator login email                   |
| `DEFAULT_ADMIN_PASSWORD`            | replace-required placeholder | Seeded administrator password                      |
| `STORAGE_ROOT`                      | `storage`                    | Host-run storage root                              |
| `MAX_FILE_SIZE_MB`                  | `50`                         | Future configurable upload limit                   |
| `ALLOWED_FILE_EXTENSIONS`           | `.pdf,.docx,.xlsx`           | Future upload allowlist                            |
| `MASTER_DATA_IMPORT_MAX_ROWS`       | `5000`                       | Maximum data rows accepted by one XLSX import      |
| `MASTER_DATA_EXPORT_MAX_ROWS`       | `50000`                      | Maximum rows emitted by one Master Data export     |
| `DEFAULT_COMPANY_CODE`              | `MTI`                        | Default company component for document codes       |
| `DOCUMENT_REGISTER_IMPORT_MAX_ROWS` | `10000`                      | Maximum register rows accepted by one XLSX import  |
| `DOCUMENT_REGISTER_EXPORT_MAX_ROWS` | `100000`                     | Maximum rows emitted by one register export        |
| `DOCUMENT_IMPORT_MAX_FILE_SIZE_MB`  | `25`                         | Maximum register workbook upload size              |
| `DOCUMENT_NUMBER_MAX_LENGTH`        | `50`                         | Maximum normalized document-number length          |
| `DOCUMENT_TITLE_MAX_LENGTH`         | `500`                        | Maximum document-title length                      |
| `ARCHIVE_REASON_MAX_LENGTH`         | `1000`                       | Maximum archive-reason length                      |

Docker Compose changes `DATABASE_HOST` to the internal `postgres` hostname.
`BACKEND_CORS_ORIGINS` can contain multiple comma-separated origins without
spaces.

## Running with Docker

After configuring `.env`, build and start the Phase 4 stack:

```bash
docker compose up --build -d
docker compose ps
```

Apply the database migration and create the bootstrap administrator:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.create_admin
docker compose exec backend python -m scripts.seed_master_data
```

Useful URLs:

- Login: <http://localhost:5173/login>
- Frontend application: <http://localhost:5173>
- Master Data overview: <http://localhost:5173/master-data>
- Document Register: <http://localhost:5173/documents>
- Add Document: <http://localhost:5173/documents/new>
- Archived Documents: <http://localhost:5173/documents/archived>
- Backend root: <http://localhost:8000>
- Health endpoint: <http://localhost:8000/api/v1/health>
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

Stop containers while retaining PostgreSQL data:

```bash
docker compose down
```

The `postgres_data` volume preserves database data, and the bind-mounted
`storage` directory preserves application files. PostgreSQL is intentionally
reachable only inside the Compose network. `docker compose down -v` permanently
deletes the development database volume.

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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

This direct-run workflow expects PostgreSQL at the configured `DATABASE_HOST`
and `DATABASE_PORT`. On macOS or Linux, activate the environment with:

```bash
source .venv/bin/activate
```

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
key, uniqueness constraints, lookup indexes, and Phase 4 audit actions. Apply
all pending migrations from `backend`:

```bash
alembic upgrade head
alembic current
```

To roll back only Phase 4 while retaining Phase 3 Master Data:

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
```

The script creates only missing defaults and does not replace custom
administrator data.

Default seed content:

- Departments: `HRM`, `ICT`, `FNC`, `ENV`, `PRC`, `ACP`, `CHP`, `CCP`
- Document Types: `SOP`, `WIN`, `POL`, `GUI`, `MAN`, `FRM`, `PLN`
- Document Statuses: `DRAFT`, `UNDER_REVIEW`, `APPROVED`, `EFFECTIVE`,
  `OBSOLETE`, `SUPERSEDED`
- Validation Rule: `DEFAULT-3LANG` with Indonesian, English, and Chinese
  required at 95% minimum coverage, compliance score 95, and partial score 70

Sections are intentionally not seeded because organization-specific section
codes are not yet known.

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

## Supported file formats

The product specification supports only:

- PDF (`.pdf`, `application/pdf`)
- DOCX (`.docx`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
- XLSX (`.xlsx`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)

Phase 4 recognizes these extensions only while parsing a filename string. It
accepts XLSX for Master Data or Document Register import/export, but it does not
upload or extract operational PDF, DOCX, or XLSX content. Physical upload,
extraction, and language validation remain future work.

## Quality checks

Backend:

```bash
cd backend
pytest
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
```

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

**The backend cannot connect to PostgreSQL.** For a host-run backend,
`DATABASE_HOST` should normally be `localhost`. Compose overrides it with
`postgres`. Check `docker compose logs postgres`.

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
docker compose up --build -d frontend backend
```

Phase 4 is complete only when the Phase 1-3 regression suite, migration and
both seeds, health and authentication checks, Master Data workflows, Document
Register CRUD and revisions, scoped XLSX import/export, frontend
lint/tests/build, and Docker smoke checks all pass. Physical document upload,
content extraction, and language validation remain intentionally outside this
release.
