# Document Compliance & Multilingual Validation System

Sistem pengendalian dokumen internal untuk mendaftarkan dokumen dan revisinya,
menyimpan file secara privat, mengekstrak isi PDF/DOCX/XLSX, menjalankan OCR
lokal, mendeteksi bahasa Indonesia, Inggris, dan Simplified Chinese (`zh`),
serta
memvalidasi kepatuhan struktur dokumen multibahasa.

Versi saat ini: **1.0.0 (Phase 1-10)**.

> Aplikasi bersifat non-destructive: aplikasi tidak menerjemahkan, mengedit,
> atau menimpa isi dokumen sumber. Hasil OCR, deteksi bahasa, similarity, dan
> compliance adalah bukti bantu untuk proses review, bukan pengganti keputusan
> pengendali dokumen atau reviewer.

## Daftar isi

- [Fitur utama](#fitur-utama)
- [Alur aplikasi](#alur-aplikasi)
- [Arsitektur](#arsitektur)
- [Mulai cepat dengan Docker](#mulai-cepat-dengan-docker)
- [Konfigurasi database](#konfigurasi-database)
- [Akun administrator dan data awal](#akun-administrator-dan-data-awal)
- [Model lokal OCR, bahasa, dan similarity](#model-lokal-ocr-bahasa-dan-similarity)
- [Panduan penggunaan](#panduan-penggunaan)
- [Role dan akses](#role-dan-akses)
- [Menjalankan development secara lokal](#menjalankan-development-secara-lokal)
- [Operasi dan pemantauan](#operasi-dan-pemantauan)
- [Quality checks](#quality-checks)
- [SharePoint dan production deployment](#sharepoint-dan-production-deployment)
- [Troubleshooting](#troubleshooting)
- [Batasan penting](#batasan-penting)
- [Dokumentasi lanjutan](#dokumentasi-lanjutan)

## Fitur utama

- Autentikasi JWT, refresh token, penguncian akun, role, dan permission.
- Master Data untuk department, organizational section, document type,
  document status, validation rule, canonical section definition, alias, dan
  glossary.
- Document Register, revision history, archive/restore, serta import/export
  XLSX.
- Upload satu atau banyak file dengan preview identifikasi sebelum data
  disimpan permanen.
- Validasi ekstensi, MIME, signature, struktur OOXML, ukuran, dan SHA-256
  duplicate detection.
- Penyimpanan file privat dengan riwayat replace, soft delete, restore, dan
  authenticated download.
- Ekstraksi isi PDF, DOCX, dan XLSX ke struktur container/block/table yang
  dinormalisasi.
- OCR lokal untuk PDF hasil scan menggunakan PaddleOCR.
- Deteksi bahasa lokal berbasis fastText dan aturan Unicode untuk `id`, `en`,
  dan `zh`, termasuk hasil `unknown` dan `other`.
- Compliance validation untuk keberadaan bahasa, canonical section, urutan
  bahasa, translation group, dan tabel.
- Finding workflow, translation similarity, glossary validation, revision
  comparison, serta laporan XLSX/JSON/PDF.
- Integrasi Microsoft Graph/SharePoint, notification channels, retention,
  metrics, health monitoring, dan production hardening.
- Audit trail untuk perubahan dan tindakan penting.

### Status pengembangan

| Phase | Ruang lingkup                                       | Status  |
| ----- | --------------------------------------------------- | ------- |
| 1     | React, FastAPI, PostgreSQL, Alembic, Docker         | Selesai |
| 2     | Authentication, authorization, application layout   | Selesai |
| 3     | Master Data management                              | Selesai |
| 4     | Document Register dan revision management           | Selesai |
| 5     | Upload dan identifikasi dokumen fisik               | Selesai |
| 6     | Ekstraksi PDF, DOCX, XLSX                           | Selesai |
| 7     | OCR dan deteksi bahasa                              | Selesai |
| 8     | Multilingual compliance dan findings                | Selesai |
| 9     | Similarity, glossary, revision comparison, reports  | Selesai |
| 10    | SharePoint, notifications, dan production hardening | Selesai |

## Alur aplikasi

Alur operasional utama:

```text
Login
  -> Siapkan Master Data
  -> Upload dan identifikasi file
  -> Konfirmasi document/revision
  -> Extract Content
  -> OCR jika PDF hasil scan
  -> Detect Languages
  -> Validate Compliance
  -> Review Findings
  -> Similarity / Glossary / Revision Comparison
  -> Reports
  -> SharePoint (opsional)
```

Secara default proses intelligence dijalankan manual agar setiap hasil dapat
ditinjau:

```dotenv
AUTO_RUN_OCR_AFTER_EXTRACTION=false
AUTO_RUN_LANGUAGE_DETECTION_AFTER_EXTRACTION=false
AUTO_RUN_LANGUAGE_DETECTION_AFTER_OCR=false
```

Tidak ada auto-chain bawaan untuk compliance, similarity, glossary, atau
revision comparison.

## Arsitektur

```text
Browser
  |
  v
React + Vite / Nginx :5173
  |
  | /api/v1
  v
FastAPI :8000
  |---- PostgreSQL       metadata, hasil proses, audit trail
  |---- Redis            broker dan result backend
  |---- Private Storage  file asli dan report snapshot
  |
  +---- Celery workers
          extraction
          OCR
          language detection
          compliance
          similarity
          glossary
          revision comparison
          reporting
          SharePoint
          notifications
          maintenance

FastAPI / workers
  |
  +---- Microsoft Graph / SharePoint Online (opsional, default nonaktif)
```

Frontend menyembunyikan menu sesuai permission untuk kenyamanan pengguna.
Backend tetap menjadi sumber kebenaran untuk authorization dan department
scope.

### Teknologi

| Layer      | Teknologi                                                         |
| ---------- | ----------------------------------------------------------------- |
| Frontend   | React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand |
| Backend    | Python 3.12, FastAPI, Pydantic                                    |
| Database   | PostgreSQL 16, SQLAlchemy 2 async, asyncpg, Alembic               |
| Queue      | Redis 7, Celery                                                   |
| Extraction | PyMuPDF, python-docx, openpyxl                                    |
| OCR        | PaddleOCR, PaddlePaddle, OpenCV                                   |
| Language   | fastText `lid.176`, Unicode/lexical rules                         |
| Similarity | sentence-transformers, PyTorch, scikit-learn, RapidFuzz           |
| Reporting  | openpyxl, ReportLab                                               |
| Deployment | Docker, Docker Compose, Nginx                                     |

### Worker dan queue

| Service Compose        | Queue default         | Tugas utama                         |
| ---------------------- | --------------------- | ----------------------------------- |
| `worker`               | `extraction`          | Ekstraksi PDF/DOCX/XLSX             |
| `worker-ocr`           | `ocr`                 | OCR PDF hasil scan                  |
| `worker-language`      | `language`            | Deteksi bahasa                      |
| `worker-compliance`    | `compliance`          | Multilingual compliance             |
| `worker-similarity`    | `similarity`          | Translation similarity              |
| `worker-glossary`      | `glossary`            | Glossary validation                 |
| `worker-revision`      | `revision-comparison` | Perbandingan revision               |
| `worker-reporting`     | `reporting`           | Report dan snapshot                 |
| `worker-sharepoint`    | `sharepoint`          | SharePoint synchronization          |
| `worker-notifications` | `notifications`       | In-app dan remote notification      |
| `worker-maintenance`   | `maintenance`         | Retention dan maintenance jobs      |
| `celery-beat`          | -                     | Menjadwalkan periodic Phase 10 jobs |

## Mulai cepat dengan Docker

### Prasyarat

- Docker Desktop atau Docker Engine dengan Docker Compose v2.
- Git.
- RAM dan ruang disk yang memadai untuk image Python/ML dan model lokal.

Node.js dan Python host hanya diperlukan untuk development tanpa container.

### 1. Buat file environment

Jalankan dari root repository:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Ubah semua placeholder `REPLACE_ME_...`, terutama:

```dotenv
POSTGRES_PASSWORD=<strong-local-database-password>
JWT_SECRET_KEY=<generated-random-value-at-least-32-characters>
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_PASSWORD=<unique-password-from-a-password-manager>
```

Gunakan password manager untuk password database/admin. Buat JWT secret acak,
misalnya dengan `openssl rand -hex 32`. Alternatif PowerShell:

```powershell
$secretBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($secretBytes)
[System.BitConverter]::ToString($secretBytes).Replace('-', '').ToLowerInvariant()
$rng.Dispose()
```

Password administrator minimal delapan karakter serta mengandung huruf besar,
huruf kecil, dan angka.

Jangan memakai placeholder secara literal dan jangan commit `.env` atau
credential asli.

### 2. Pilih database

Untuk PostgreSQL bawaan Docker:

```dotenv
POSTGRES_DB=document_compliance
POSTGRES_USER=document_compliance
POSTGRES_PASSWORD=<strong-local-database-password>

DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_NAME=document_compliance
DATABASE_USER=document_compliance
DATABASE_PASSWORD=<same-local-database-password>
```

Untuk database eksternal, lihat
[Konfigurasi database](#konfigurasi-database). Nilai `DATABASE_*` menentukan
database yang benar-benar digunakan aplikasi.

### 3. Build dan jalankan service

```bash
docker compose up --build -d
docker compose ps
```

Compose menjalankan 16 service: PostgreSQL, Redis, backend, frontend, sebelas
worker khusus, dan Celery Beat.

### 4. Buat schema dan data awal

Migrasi dan seed tidak dijalankan otomatis pada development stack:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.create_admin
docker compose exec backend python -m scripts.seed_master_data
docker compose exec backend python -m scripts.seed_section_definitions
```

Semua perubahan schema harus melalui Alembic. Jangan membuat tabel aplikasi
secara manual.

### 5. Verifikasi

```bash
docker compose exec backend alembic current
docker compose ps
docker compose exec worker celery -A app.workers.celery_app inspect ping
```

Alembic harus berada pada revision `20260726_0010 (head)`. Service aplikasi dan
worker harus berstatus `healthy`.

URL development:

| Layanan    | URL                                   |
| ---------- | ------------------------------------- |
| Login      | <http://localhost:5173/login>         |
| Aplikasi   | <http://localhost:5173>               |
| API        | <http://localhost:8000>               |
| Swagger UI | <http://localhost:8000/docs>          |
| ReDoc      | <http://localhost:8000/redoc>         |
| API health | <http://localhost:8000/api/v1/health> |
| Liveness   | <http://localhost:8000/health/live>   |
| Readiness  | <http://localhost:8000/health/ready>  |

`/api/v1/health` dan `/health/live` adalah liveness ringan. Gunakan
`/health/ready` untuk memastikan database, dependency wajib, dan heartbeat
seluruh worker benar-benar siap.

## Konfigurasi database

Ada dua kelompok konfigurasi database:

| Variabel     | Fungsi                                                |
| ------------ | ----------------------------------------------------- |
| `POSTGRES_*` | Menginisialisasi container PostgreSQL bawaan          |
| `DATABASE_*` | Menentukan target database backend dan seluruh worker |

`DATABASE_NAME`, `DATABASE_USER`, dan `DATABASE_PASSWORD` dapat dibuat berbeda
dari `POSTGRES_*`. Jika tidak diisi, application credential tersebut jatuh ke
nilai `POSTGRES_*`. `DATABASE_HOST` menggunakan `postgres` untuk database
bawaan Compose.

### Database eksternal

Contoh:

```dotenv
# Tetap diperlukan oleh service PostgreSQL bawaan pada docker-compose.yml.
POSTGRES_DB=document_compliance
POSTGRES_USER=document_compliance
POSTGRES_PASSWORD=<strong-local-container-password>

# Target aplikasi yang sebenarnya.
DATABASE_HOST=db.internal.example
DATABASE_PORT=5432
DATABASE_NAME=trilingual-checker
DATABASE_USER=document_compliance
DATABASE_PASSWORD=<strong-external-database-password>
```

User database eksternal harus memiliki hak `CONNECT`, akses ke schema
aplikasi, dan hak DDL yang diperlukan Alembic untuk membuat atau mengubah
schema. Gunakan account aplikasi khusus; jangan menjalankan aplikasi harian
dengan superuser PostgreSQL.

Setelah mengganti `.env`, recreate container agar environment baru digunakan:

```bash
docker compose up -d --force-recreate
```

Tampilkan target database aktif tanpa menampilkan password:

```bash
docker compose exec backend python -c "from app.core.config import get_settings; s=get_settings(); print(f'{s.database_host}:{s.database_port}/{s.postgres_db} as {s.postgres_user}')"
```

Lalu pastikan migrasi diterapkan pada target tersebut:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

Query verifikasi dari DBeaver/psql:

```sql
SELECT current_database(), current_user, current_schema();

SELECT count(*) AS public_table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';

SELECT version_num
FROM alembic_version;
```

Jika DBeaver belum menampilkan tabel, pastikan koneksi membuka
`DATABASE_NAME`, pilih schema `public`, lalu lakukan refresh/reconnect.

> Mengubah `POSTGRES_PASSWORD` setelah volume PostgreSQL bawaan pernah dibuat
> tidak otomatis mengubah password role di dalam database. Rotasi password
> role melalui PostgreSQL. Jangan menggunakan `docker compose down -v` kecuali
> seluruh data development memang boleh dihapus.

## Akun administrator dan data awal

Bootstrap administrator berasal dari:

```dotenv
DEFAULT_ADMIN_NAME=System Administrator
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_PASSWORD=<unique-password-from-a-password-manager>
```

Script `create_admin` bersifat idempotent: account dibuat hanya jika belum ada.
Mengganti `DEFAULT_ADMIN_PASSWORD` setelah account terbentuk **tidak mereset
password account yang sudah ada**.

Seed Master Data membuat default berikut:

- Departments: `HRM`, `ICT`, `FNC`, `ENV`, `PRC`, `ACP`, `CHP`, `CCP`.
- Document Types: `SOP`, `WIN`, `POL`, `GUI`, `MAN`, `FRM`, `PLN`.
- Document Statuses: `DRAFT`, `UNDER_REVIEW`, `APPROVED`, `EFFECTIVE`,
  `OBSOLETE`, `SUPERSEDED`.
- Validation Rule: `DEFAULT-3LANG`.
- 12 canonical section definitions dan 46 alias Indonesia/Inggris/Simplified
  Chinese.

`Sections` organisasi sengaja tidak di-seed karena nilainya khusus tiap
department. Seluruh document type default memiliki `requiresSection=true`, jadi
administrator harus membuat section organisasi sebelum memakai document type
tersebut. Ini berbeda dari `Section Definitions`:

- **Sections** adalah bagian organisasi yang dapat menjadi komponen kode
  dokumen, misalnya section di dalam department.
- **Section Definitions** adalah heading/struktur isi yang divalidasi, misalnya
  Purpose, Scope, Definition, Responsibility, atau Procedure.

Seed juga tidak membuat dokumen bisnis contoh. Tabel document, revision, file,
extraction, dan compliance baru terisi setelah pengguna membuat atau
mengunggah dokumen.

## Model lokal OCR, bahasa, dan similarity

Fitur inti aplikasi tetap dapat dibuka tanpa model ML, tetapi proses OCR,
deteksi bahasa, dan translation similarity memerlukan model lokal. Aplikasi
tidak mengunduh model saat startup.

Setelah image backend selesai dibangun, jalankan dari root repository untuk
memasang model secara eksplisit dengan Docker:

```powershell
docker compose run --rm --no-deps --user root --volume "${PWD}/models:/app/models" backend python scripts/download_ocr_models.py --model-root /app/models/ocr
docker compose run --rm --no-deps --user root --volume "${PWD}/models:/app/models" backend python scripts/download_language_model.py --path /app/models/language/lid.176.bin
docker compose run --rm --no-deps --user root --volume "${PWD}/models:/app/models" backend python scripts/download_similarity_model.py
```

Pada Linux, command one-off tersebut dapat membuat file milik `root` pada bind
mount. Setelah instalasi, kembalikan ownership ke user host bila diperlukan:

```bash
sudo chown -R "$(id -u):$(id -g)" models
```

Verifikasi similarity model tanpa akses jaringan:

```powershell
docker compose run --rm --no-deps --user root --volume "${PWD}/models:/app/models" backend python scripts/download_similarity_model.py --offline-verify
```

Setelah instalasi, restart worker terkait:

```bash
docker compose restart worker-ocr worker-language worker-similarity
```

Direktori `models/` di-mount read-only ke runtime worker dan tidak boleh
di-commit ke repository.

## Panduan penggunaan

### 1. Login

Buka <http://localhost:5173/login>, lalu login memakai email dan password
administrator yang digunakan saat menjalankan `create_admin`.

### 2. Lengkapi Master Data

Buka menu **Master Data** dan periksa:

1. Departments.
2. Sections organisasi. Seluruh document type hasil seed default memerlukan
   section, jadi buat sedikitnya satu section yang sesuai di department terkait
   sebelum registrasi atau upload dokumen.
3. Document Types.
4. Document Statuses.
5. Validation Rules.
6. Section Definitions dan aliases.
7. Glossary profiles/terms bila glossary validation akan dipakai.

### 3. Masukkan dokumen

Cara yang direkomendasikan:

1. Buka **Documents > Upload Document**.
2. Pilih file PDF, DOCX, atau XLSX.
3. Klik **Upload and Identify**.
4. Periksa hasil identifikasi.
5. Klik **Review Action**.
6. Pilih action, lengkapi metadata, lalu konfirmasi.

Action yang tersedia:

- **Create document and first revision** untuk dokumen baru.
- **Attach to existing revision** jika revision sudah ada tetapi belum
  memiliki file utama.
- **Add as a new revision** jika isi atau versi bisnis berubah.
- **Replace current file** hanya untuk mengganti file pada revision yang sama;
  alasan wajib diisi dan file lama tetap tercatat dalam history.
- **Skip** untuk tidak memproses item.

`MANUAL_REVIEW` adalah status proposal ketika nama file ambigu, bukan action
akhir.

Format nama file yang membantu identifikasi otomatis:

```text
MTI-HRM-IER-POL-001_Rev.000.pdf
MTI-HRM-IER-SOP-001_Rev.000.docx
MTI-HRM-IER-SOP-001_Rev. 000 - Demin Plant - Judul 中文.pdf
```

Suffix judul opsional setelah separator ` - ` ikut dipakai untuk mengisi
**Document Title**. Judul boleh mengandung spasi, simbol yang aman, dan
Unicode; bagian
kode/revisi tetap dinormalisasi menjadi bentuk canonical seperti
`MTI-HRM-IER-SOP-001_Rev.000`.

Pada contoh tersebut, section `IER` harus sudah dibuat di department `HRM`.
Nama yang tidak sesuai masih dapat diproses melalui identifikasi manual.
Default batas file adalah 50 MB. Batch upload tersedia di **Documents > Batch
Upload**.

Alternatif metadata-first:

1. Buka **Documents > Add Document**.
2. Buat record dan revision awal.
3. Buka detail document.
4. Pada tab **Files**, upload file ke current revision.

### 4. Extract Content

Pada detail document:

1. Buka tab **Files**.
2. Jalankan **Extract Content** pada current file.
3. Pantau **Extraction Queue** atau **Extraction History**.

PDF dengan selectable text diproses langsung. PDF yang sebagian besar berupa
gambar dapat menghasilkan status `OCR_REQUIRED`.

### 5. Jalankan OCR bila diperlukan

Pada tab **Intelligence**, jalankan **Run OCR** hanya untuk current PDF yang
eligible. DOCX dan XLSX tidak di-OCR karena keduanya menggunakan native
extraction.

Pilih profile Latin, Simplified Chinese, atau multilingual sesuai isi scan.
Periksa confidence dan halaman yang perlu review.

### 6. Detect Languages

Setelah extraction selesai, atau setelah OCR selesai untuk PDF scan:

1. Buka tab **Intelligence**.
2. Klik **Detect Languages**.
3. Periksa bahasa, confidence, block coverage, dan character coverage.

Deteksi bahasa tidak menerjemahkan teks dan tidak membuktikan kesetaraan
terjemahan.

### 7. Validate Compliance

Prasyaratnya:

- current physical file tersedia;
- extraction selesai;
- OCR selesai jika diwajibkan;
- language detection selesai; dan
- revision memiliki validation rule.

Buka tab **Compliance**, lalu jalankan **Validate Compliance**. Hasil
menampilkan ringkasan score/status, language coverage, sections, language
order, translation groups, findings, dan validation history.

Revalidation membuat run baru. Hasil historis tidak ditimpa.

### 8. Review Findings

Lifecycle utama:

```text
OPEN / REOPENED
  -> IN_REVIEW
  -> RESOLVED | FALSE_POSITIVE | ACCEPTED_RISK
```

Finding terminal dapat dibuka kembali menjadi `REOPENED`. Revalidation atau
revision comparison tidak menutup finding secara otomatis.

### 9. Quality

Tab **Quality** menyediakan:

- **Translation Similarity** setelah extraction, language detection, dan
  compliance grouping tersedia.
- **Glossary Validation** setelah glossary profile/term disiapkan.
- **Revision Comparison** jika document memiliki sedikitnya dua revision
  dengan evidence pemrosesan yang kompatibel.

Similarity adalah review signal, bukan bukti bahwa terjemahan benar secara
linguistik atau legal. Quality score terpisah dan tidak menimpa compliance
score historis.

### 10. Reports dan SharePoint

Menu **Reports** menyediakan compliance, findings, translation similarity,
glossary, revision changes, advanced analytics, snapshot, dan schedule.
Snapshot disimpan privat dan diunduh melalui endpoint terautentikasi.

Report schedule saat ini adalah konfigurasi yang dijalankan melalui
**Run Now/manual**, bukan pengiriman report otomatis.

SharePoint bersifat opsional dan nonaktif secara default. Konfigurasikan
Microsoft Entra/Graph, connection, folder mapping, metadata mapping, dan sync
profile sebelum menjalankan sync. Document/Revision/File internal tetap
menjadi business source of truth.

## Role dan akses

| Role                  | Akses utama                                                                                                                                                      |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SUPER_ADMIN`         | Seluruh permission, users, Master Data, integrations, system health, retention, dan administration                                                               |
| `DOCUMENT_CONTROLLER` | Workflow document harian lintas department: register, upload, extraction, OCR, language, compliance, findings, quality, reports, dan sync; Master Data read-only |
| `REVIEWER`            | Read sesuai scope, review/resolve/reopen/false-positive findings, serta quality review                                                                           |
| `DEPARTMENT_USER`     | Create/update/upload dan proses awal hanya untuk department sendiri; tanpa administrasi atau replace/delete file                                                 |
| `AUDITOR`             | Read/export/audit data bisnis lintas department; dapat mengatur notification preference miliknya                                                                 |
| `VIEWER`              | Read-only untuk data bisnis sesuai scope; dapat mengatur notification preference miliknya                                                                        |

Menu dan tombol difilter berdasarkan permission. Request langsung ke API tetap
divalidasi ulang oleh backend.

## Menjalankan development secara lokal

### Backend

Siapkan PostgreSQL dan Redis, lalu sesuaikan `DATABASE_HOST`, `REDIS_HOST`,
`CELERY_BROKER_URL`, dan `CELERY_RESULT_BACKEND` untuk host. Contoh:

```dotenv
DATABASE_HOST=localhost
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL=false
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
python -m scripts.create_admin
python -m scripts.seed_master_data
python -m scripts.seed_section_definitions
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Jika command dijalankan dari `backend/`, gunakan path host yang sesuai:

```dotenv
STORAGE_ROOT=../storage
OCR_MODEL_ROOT=../models/ocr
LANGUAGE_MODEL_PATH=../models/language/lid.176.bin
SIMILARITY_MODEL_PATH=../models/similarity
```

Worker lokal dijalankan dari terminal backend terpisah. Contoh:

```bash
celery -A app.workers.celery_app worker --loglevel=INFO --queues=extraction --concurrency=2 --hostname="extraction@%h"
celery -A app.workers.celery_app worker --loglevel=INFO --queues=ocr --concurrency=1 --hostname="ocr@%h"
celery -A app.workers.celery_app worker --loglevel=INFO --queues=language --concurrency=2 --hostname="language@%h"
celery -A app.workers.celery_app worker --loglevel=INFO --queues=compliance --concurrency=2 --hostname="compliance@%h"
```

Command di atas hanya contoh empat queue inti. Untuk full host-run stack,
jalankan satu worker untuk setiap queue pada tabel
[Worker dan queue](#worker-dan-queue), menggunakan concurrency dari
`.env.example`. Queue tanpa worker akan tetap `QUEUED`.

Jalankan periodic Phase 10 jobs dari terminal terpisah:

```powershell
New-Item -ItemType Directory -Force ..\storage\celerybeat | Out-Null
celery -A app.workers.celery_app beat --loglevel=INFO --schedule=../storage/celerybeat/celerybeat-schedule
```

Pada macOS/Linux, buat direktori yang sama dengan
`mkdir -p ../storage/celerybeat`.

Docker Compose direkomendasikan untuk menjalankan seluruh worker. OCR dan
similarity sengaja memakai concurrency rendah karena model lokal membutuhkan
memori lebih besar.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Prasyarat host:

- Node.js 22.22 atau lebih baru.
- npm 10 atau lebih baru.
- Python 3.12 atau lebih baru.

## Operasi dan pemantauan

### Status dan log

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f worker-ocr
docker compose logs -f worker-language
docker compose logs -f worker-compliance
```

Satu perintah Celery inspect dapat melihat worker yang terhubung ke broker:

```bash
docker compose exec worker celery -A app.workers.celery_app inspect ping
```

### Restart atau rebuild

Restart tanpa build:

```bash
docker compose restart backend frontend
```

Build ulang setelah source/dependency berubah:

```bash
docker compose up --build -d
```

### Stop

```bash
docker compose down
```

Perintah tersebut mempertahankan volume database/Redis dan isi bind mount
`storage/`.

> `docker compose down -v` menghapus volume development. Jangan jalankan
> perintah itu pada data yang masih diperlukan.

## Quality checks

Backend:

```bash
cd backend
python -m ruff check app alembic scripts
python -m mypy app --exclude 'app[\\/]tests' --ignore-missing-imports --no-incremental
python -W error -m pytest
```

Frontend:

```bash
cd frontend
npm ci
npm run format:check
npm run lint
npm test
npm run build
```

End-to-end:

```bash
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

Compose:

```bash
docker compose config
docker compose ps
```

CI juga menjalankan migration checks, dependency audit, secret scanning, dan
container image checks melalui workflow di `.github/workflows/`.

## SharePoint dan production deployment

Microsoft Graph dan SharePoint nonaktif secara default:

```dotenv
MICROSOFT_GRAPH_ENABLED=false
SHAREPOINT_SYNC_ENABLED=false
```

Aktivasi memerlukan:

1. Microsoft Entra application.
2. Admin consent.
3. Permission minimum `Sites.Selected` dan grant pada site target.
4. Certificate untuk production; client secret hanya cocok untuk development
   yang dikendalikan.
5. SharePoint connection dan mapping di aplikasi.
6. Public HTTPS endpoint jika webhook digunakan.

Mulai dari:

- [SharePoint setup](docs/sharepoint-setup.md)
- [Microsoft Graph permissions](docs/microsoft-graph-permissions.md)
- [SharePoint sync design](docs/sharepoint-sync-design.md)
- [Conflict resolution](docs/sharepoint-conflict-resolution.md)

Untuk production, gunakan `.env.production.example` dan
`docker-compose.production.yml`. Jangan memakai konfigurasi development secara
langsung:

```bash
docker compose --env-file .env.production \
  -f docker-compose.production.yml build

docker compose --env-file .env.production \
  -f docker-compose.production.yml run --rm migrate

docker compose --env-file .env.production \
  -f docker-compose.production.yml run --rm migrate \
  python -m scripts.create_admin

docker compose --env-file .env.production \
  -f docker-compose.production.yml run --rm migrate \
  python -m scripts.seed_master_data

docker compose --env-file .env.production \
  -f docker-compose.production.yml run --rm migrate \
  python -m scripts.seed_section_definitions

docker compose --env-file .env.production \
  -f docker-compose.production.yml up -d
```

Production Compose saat ini menargetkan service PostgreSQL internal bernama
`postgres`. Jika production harus memakai database eksternal, siapkan dan
review Compose override khusus; jangan menganggap perubahan
`DATABASE_HOST` di `.env.production` saja sudah mengubah target.

Baca [Production deployment](docs/production-deployment.md) dan
[Operational runbook](docs/operational-runbook.md) sebelum deployment nyata.

## Troubleshooting

### Database terlihat kosong atau tabel tidak ada

1. Periksa target database aktif dengan command aman pada bagian
   [Konfigurasi database](#konfigurasi-database).
2. Pastikan `DATABASE_NAME` sama dengan database yang dibuka di DBeaver.
3. Jalankan `docker compose exec backend alembic upgrade head`.
4. Jalankan seed admin dan Master Data.
5. Refresh schema `public` di DBeaver.

Master Data seed tidak membuat dokumen bisnis. Document-related tables tetap
kosong sampai upload/import pertama.

### Login gagal

- Gunakan `DEFAULT_ADMIN_EMAIL`.
- Gunakan password yang berlaku saat `create_admin` pertama kali dijalankan.
- Perubahan password pada `.env` tidak mereset account yang sudah ada.
- Setelah terlalu banyak percobaan gagal, tunggu sesuai
  `ACCOUNT_LOCK_MINUTES`.

### Perubahan `.env` tidak masuk ke container

```bash
docker compose up -d --force-recreate
```

Periksa hasilnya menggunakan command target database atau `docker compose
config`. Jangan menampilkan hasil `config` di tempat publik karena environment
dapat mengandung credential.

### Backend unhealthy

```bash
docker compose ps
docker compose logs backend
```

Periksa database, Redis, `JWT_SECRET_KEY`, host/CORS, storage permission, lalu
akses `/api/v1/health`, `/health/live`, dan `/health/ready`.

### Job berhenti di `QUEUED`

Pastikan Redis dan worker queue yang tepat sehat:

```bash
docker compose exec worker celery -A app.workers.celery_app inspect ping
docker compose logs worker-ocr
docker compose logs worker-language
docker compose logs worker-compliance
```

Worker harus memakai queue name yang sama dengan backend.

### PDF menghasilkan `OCR_REQUIRED`

PDF tidak memiliki selectable text yang cukup. Jalankan OCR pada current PDF,
tunggu selesai, lalu jalankan language detection.

### Model tidak tersedia

Jalankan installer eksplisit pada bagian
[Model lokal OCR, bahasa, dan similarity](#model-lokal-ocr-bahasa-dan-similarity),
pastikan file ada di `models/`, lalu restart worker terkait.

### Browser menampilkan CORS error

Masukkan origin frontend yang tepat ke `BACKEND_CORS_ORIGINS`, termasuk
protocol dan port, lalu recreate backend.

### File upload ditolak

Periksa:

- format hanya `.pdf`, `.docx`, atau `.xlsx`;
- default ukuran maksimal 50 MB;
- MIME/signature sesuai extension;
- file OOXML tidak rusak;
- SHA-256 duplicate acknowledgement;
- permission dan department scope pengguna.

## Batasan penting

- OCR hanya untuk PDF. Image standalone, PPTX, dan format lain belum didukung.
- DOCX dan XLSX menggunakan native extraction; formula XLSX tidak dieksekusi.
- OCR bergantung pada kualitas scan, orientasi, profile, dan model lokal.
- Deteksi bahasa pada teks pendek/teknis dapat menghasilkan `unknown`.
- Structural grouping dan similarity tidak membuktikan kesetaraan terjemahan.
- Aplikasi tidak melakukan automatic translation atau source editing.
- Full document approval workflow, digital signature, dan public file URL tidak
  tersedia.
- Report schedule dijalankan manual melalui **Run Now**.
- SharePoint, email, Teams, Telegram, dan webhook memerlukan layanan eksternal
  serta nonaktif secara default.
- Malware scanning memerlukan ClamAV eksternal dan konfigurasi khusus; tidak
  boleh dianggap aktif hanya karena file berhasil di-upload.
- Real Microsoft 365 tenant, certificate, DNS/TLS, admin consent, backup policy,
  RPO, dan RTO tetap menjadi tanggung jawab deployment.

## Struktur repository

```text
document-compliance-system/
|-- backend/                    FastAPI, SQLAlchemy, Alembic, Celery, tests
|-- frontend/                   React, TypeScript, Vite, tests
|-- docs/                       deployment dan integration runbooks
|-- models/                     model lokal, tidak di-commit
|-- sample-documents/           fixture sintetis tanpa data perusahaan
|-- scripts/                    backup, restore, dan operational scripts
|-- storage/                    private local storage, tidak dipublikasi
|-- docker-compose.yml          development stack
|-- docker-compose.production.yml
|-- .env.example
|-- .env.development.example
`-- .env.production.example
```

## Dokumentasi lanjutan

| Topik                | Dokumen                                                                  |
| -------------------- | ------------------------------------------------------------------------ |
| Quality intelligence | [Phase 9 quality intelligence](docs/phase9-quality-intelligence.md)      |
| SharePoint setup     | [SharePoint setup](docs/sharepoint-setup.md)                             |
| Graph permission     | [Microsoft Graph permissions](docs/microsoft-graph-permissions.md)       |
| Sync architecture    | [SharePoint sync design](docs/sharepoint-sync-design.md)                 |
| Conflict handling    | [SharePoint conflict resolution](docs/sharepoint-conflict-resolution.md) |
| Notifications        | [Notification operations](docs/notifications.md)                         |
| Security             | [Security hardening](docs/security-hardening.md)                         |
| Monitoring           | [Monitoring and alerting](docs/monitoring-and-alerting.md)               |
| Retention            | [Retention policy](docs/retention-policy.md)                             |
| Production           | [Production deployment](docs/production-deployment.md)                   |
| Operations           | [Operational runbook](docs/operational-runbook.md)                       |
| Backup               | [Backup and restore](docs/backup-and-restore.md)                         |
| Disaster recovery    | [Disaster recovery](docs/disaster-recovery.md)                           |
