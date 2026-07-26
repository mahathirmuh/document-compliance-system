# Phase 9 quality intelligence

Version 0.9.0 adds local translation-similarity signals, glossary validation,
revision comparison, and advanced report snapshots to the retained Phase 8
compliance evidence. It does not translate, rewrite, or approve a source
document.

## Processing and privacy boundary

```text
Retained extraction/OCR/language/compliance evidence
  |-- translation groups --> similarity worker --> pair results + findings
  |-- normalized blocks --> glossary worker --> matches + findings
  |-- two revisions ------> revision worker --> aligned changes + comparisons
  `-- scoped database data -> reporting worker -> private report snapshot
```

All document-content processing is local. Runtime workers do not call a cloud
AI, translation, or OCR API. Model and storage paths are operational
configuration and are not returned by public APIs. Embeddings are used in
memory and are not persisted or exposed. Downloads remain authenticated and
department scoped. Reports omit full document text by default and retain only
bounded snippets where a report needs context.

Similarity is a review signal, not legal evidence. A high score does not prove
that a translation is correct, and a low score does not automatically create a
Critical finding.

## Translation similarity

The provider is `sentence_transformer`, using the local
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` model on CPU by
default. The worker resolves Phase 8 translation groups and compares the
default pairs:

- Indonesian–English (`id-en`)
- Indonesian–Chinese (`id-zh`)
- English–Chinese (`en-zh`)

Each result retains source provenance, language pair, model metadata, text
hashes, bounded snippets, score, category, confidence, length ratio,
consistency results, and chunk statistics. Raw embedding vectors are not
stored.

Default similarity categories are:

| Category        | Score                  |
| --------------- | ---------------------- |
| `HIGH`          | `>= 0.85`              |
| `ACCEPTABLE`    | `>= 0.72` and `< 0.85` |
| `NEEDS_REVIEW`  | `>= 0.58` and `< 0.72` |
| `LOW`           | `< 0.58`               |
| `NOT_EVALUATED` | no reliable score      |

`SIMILARITY_CRITICAL_LOW_THRESHOLD=0.35` is additional evidence for finding
classification; it does not make the finding Critical by itself.

Confidence is separate from semantic similarity. The current calculation is
a bounded weighted signal:

```text
30% translation-group confidence
25% mean source/target language confidence
15% shortest-text sufficiency (saturates at 100 characters)
15% chunk completeness
15% minimum extraction/OCR quality
```

Text under `SIMILARITY_MIN_CHARACTERS_PER_TEXT` and optionally code-like or
numeric-only text is not evaluated. Long content is bounded to 12,000
characters by default, split near paragraph/sentence boundaries into
1,500-character chunks with a 150-character overlap, and capped at 50 chunks.
The worker averages chunk embeddings before cosine comparison and records a
warning when truncation occurs.

Deterministic consistency services compare:

- numbers;
- dates;
- measurements and units;
- document references;
- language-specific negation cues; and
- source/target length ratios.

Negation detection is deliberately conservative. It creates a possible
mismatch/review signal because morphology and context can make a keyword-only
decision ambiguous.

Similarity finding codes are:

```text
LOW_TRANSLATION_SIMILARITY
TRANSLATION_SIMILARITY_NEEDS_REVIEW
TRANSLATION_NOT_EVALUATED
TRANSLATION_LENGTH_RATIO_ANOMALY
TRANSLATION_NUMBER_MISMATCH
TRANSLATION_DATE_MISMATCH
TRANSLATION_MEASUREMENT_MISMATCH
TRANSLATION_REFERENCE_MISMATCH
TRANSLATION_NEGATION_MISMATCH
TRANSLATION_CONTENT_TOO_SHORT
TRANSLATION_MODEL_UNAVAILABLE
```

## Local model setup and offline behavior

The application never downloads this model during API or worker startup.
Install it only through the explicit operator command:

```bash
cd backend
python scripts/download_similarity_model.py
```

With the default environment, the downloaded directory is:

```text
<repository>/models/similarity/sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2
```

The host fallback above applies only when `SIMILARITY_MODEL_PATH` is unset.
Compose sets it to `/app/models/similarity`, which maps to the same repository
`./models` directory.

Verify an existing installation without network access:

```bash
cd backend
python scripts/download_similarity_model.py --offline-verify
```

In Compose, `./models` is mounted read-only into runtime workers, so the model
survives container recreation and is not downloaded on restart. A missing or
incompatible model causes a controlled failed/not-evaluated result; it does not
fall back to the internet.

## Glossary architecture

A glossary profile is resolved by the most specific active scope:

1. department plus document type;
2. department;
3. document type; and
4. global.

Profiles retain terms, per-language translations, spelling/legacy variants,
and reasoned exceptions. Term types are `PREFERRED`, `REQUIRED`, `FORBIDDEN`,
`REFERENCE`, and `ABBREVIATION`; supported translation languages are `id`,
`en`, and `zh`.

Variants can be `SYNONYM`, `ABBREVIATION`, `SPELLING`, `LEGACY`, or
`FORBIDDEN_VARIANT`. Exceptions can allow a variant, ignore a term, allow a
missing translation, or allow a forbidden term at global, department,
document, revision, file, or section scope. Every exception requires a reason,
is audited, may expire, and is department scoped. Historical glossary records
are archived rather than hard deleted.

Matching supports exact, whole-word, case-sensitive, bounded inflection,
bounded regular expression, Chinese substring, and configured variant
evidence. Regex pattern length and execution time are capped. Chinese matching
does not assume whitespace word boundaries; short or overlapping terms can
still require manual review.

The glossary importer uses an XLSX workbook with three sheets:

```text
Terms:
profile_code, term_code, concept_name, description, term_type, severity,
is_case_sensitive, match_whole_word, allow_inflection, is_regex, is_active,
notes

Translations:
term_code, language_code, term_text, is_preferred, is_forbidden, is_required,
priority, usage_note, example_text, is_active

Variants:
term_code, language_code, preferred_term_text, variant_text, variant_type,
is_allowed, is_active
```

Import is preview/confirm based and bounded by `GLOSSARY_IMPORT_MAX_ROWS`.
Export supports scoped XLSX and JSON.

Glossary finding codes are:

```text
NON_PREFERRED_GLOSSARY_TERM
FORBIDDEN_GLOSSARY_TERM
MISSING_GLOSSARY_TRANSLATION
INCONSISTENT_GLOSSARY_TRANSLATION
REQUIRED_GLOSSARY_TERM_MISSING
GLOSSARY_TERM_LANGUAGE_MISMATCH
GLOSSARY_MATCH_LOW_CONFIDENCE
GLOSSARY_EXCEPTION_EXPIRED
```

## Revision comparison

Revision comparison reads retained extraction, language, compliance,
similarity, and finding evidence for two revisions of the same document.
Canonical entity type, source reference, section, translation group,
container, normalized text, fuzzy text score, and position are used as bounded
alignment signals. The default fuzzy threshold is `0.58`; low-confidence
alignment remains visible for review.

Change types are `ADDED`, `REMOVED`, `MODIFIED`, `MOVED`, `UNCHANGED`, `SPLIT`,
and `MERGED`. The retained summary also compares:

- Indonesian, English, Chinese, and unknown language coverage;
- compliance scores, statuses, and section outcomes;
- similarity scores and pair availability;
- glossary/compliance findings; and
- finding severity or workflow-state changes.

Finding outcomes include new, no longer reproduced, repeated, severity
increased/decreased, status changed, and unchanged. “No longer reproduced” is
only a candidate-resolution signal; comparison never resolves a finding or
changes either source revision. Exports are bounded JSON, XLSX, and PDF.

## Advanced reporting

Available report types are:

```text
COMPLIANCE_OVERVIEW
FINDINGS_ANALYTICS
TRANSLATION_SIMILARITY
GLOSSARY_COMPLIANCE
REVISION_CHANGES
DEPARTMENT_PERFORMANCE
DOCUMENT_TYPE_PERFORMANCE
VALIDATION_RULE_PERFORMANCE
LANGUAGE_QUALITY
PROCESSING_PERFORMANCE
```

Filters cover date range, departments, sections, document types and statuses,
validation rules, compliance statuses, finding severities/statuses, language
pairs, glossary profiles, revision range, and archived records. The backend
intersects every request with the authenticated user's department scope.

Exports support XLSX, JSON, and PDF. Generated artifacts are private
`report_snapshots`, downloaded through an authenticated endpoint, expire after
30 days by default, and can be soft-deleted. Limits cap dataset rows, PDF table
rows, XLSX rows per sheet, chart categories, and text snippets.
`REPORT_INCLUDE_FULL_TEXT` must remain `false` in Phase 9.

Schedules retain daily, weekly, monthly, or conservatively validated five-field
cron configuration and IANA timezone metadata. Phase 9 exposes an audited
manual run endpoint that queues one snapshot per configured format. It does
not include automatic email delivery; an external schedule trigger is also not
claimed by the current manual-run implementation.

## Quality-score strategy

The default `SEPARATE_QUALITY_SCORE` mode preserves historical Phase 8
compliance scores and statuses. Translation quality is the bounded similarity
percentage. Glossary quality is the percentage of evaluated terms remaining
after forbidden, missing-translation, and inconsistent-term counts.

Validation rules default to 25% translation-similarity weight and 15% glossary
weight when an explicit combined mode is selected. The remaining percentage is
structural compliance. The selected mode and weights are retained in a
configuration snapshot. Missing required quality evidence returns
`NOT_EVALUATED`; it is not silently treated as zero.

## Workers and limits

| Compose service     | Queue                 | Concurrency | Soft/hard limit | Retries |
| ------------------- | --------------------- | ----------- | --------------- | ------- |
| `worker-similarity` | `similarity`          | 1           | 3300s / 3600s   | 1       |
| `worker-glossary`   | `glossary`            | 2           | 3300s / 3600s   | 1       |
| `worker-revision`   | `revision-comparison` | 2           | 3300s / 3600s   | 1       |
| `worker-reporting`  | `reporting`           | 1           | 3300s / 3600s   | 1       |

Run workers locally from `backend`:

```bash
celery -A app.workers.celery_app worker --loglevel=INFO --queues=similarity --concurrency=1 --hostname=similarity@%h
celery -A app.workers.celery_app worker --loglevel=INFO --queues=glossary --concurrency=2 --hostname=glossary@%h
celery -A app.workers.celery_app worker --loglevel=INFO --queues=revision-comparison --concurrency=2 --hostname=revision@%h
celery -A app.workers.celery_app worker --loglevel=INFO --queues=reporting --concurrency=1 --hostname=reporting@%h
```

The principal Phase 9 limit variables are:

```text
SIMILARITY_TEXT_MAX_CHARACTERS=12000
SIMILARITY_CHUNK_MAX_CHARACTERS=1500
SIMILARITY_CHUNK_OVERLAP_CHARACTERS=150
SIMILARITY_MAX_CHUNKS_PER_TEXT=50
SIMILARITY_DB_BATCH_SIZE=500
GLOSSARY_TERM_MAX_LENGTH=500
GLOSSARY_REGEX_MAX_LENGTH=500
GLOSSARY_REGEX_TIMEOUT_MS=100
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
REPORT_CHART_MAX_CATEGORIES=50
REPORT_TEXT_SNIPPET_MAX_CHARACTERS=500
REPORT_INCLUDE_FULL_TEXT=false
```

See `.env.example` for the complete queue, model, device, batch, threshold,
retry, and time-limit settings.

## API endpoints

All paths below are under the authenticated `/api/v1` prefix.

```text
POST /similarity/jobs
GET  /similarity/jobs
GET  /similarity/jobs/{jobId}
POST /similarity/jobs/{jobId}/cancel
GET  /similarity/runs/{runId}
GET  /similarity/runs/{runId}/summary
GET  /similarity/runs/{runId}/results
GET  /similarity/runs/{runId}/sections
GET  /similarity/runs/{runId}/export
POST /similarity/runs/{runId}/rerun
GET  /document-files/{fileId}/similarity
GET  /document-files/{fileId}/similarity-history

GET  /glossary/profiles
POST /glossary/profiles
GET  /glossary/profiles/{profileId}
PUT  /glossary/profiles/{profileId}
POST /glossary/profiles/{profileId}/archive
POST /glossary/profiles/{profileId}/restore
GET  /glossary/terms
POST /glossary/terms
GET  /glossary/terms/{termId}
PUT  /glossary/terms/{termId}
POST /glossary/terms/{termId}/archive
POST /glossary/terms/{termId}/restore
POST /glossary/terms/{termId}/translations
PUT  /glossary/translations/{translationId}
POST /glossary/translations/{translationId}/variants
PUT  /glossary/variants/{variantId}
GET  /glossary/exceptions
POST /glossary/exceptions
PUT  /glossary/exceptions/{exceptionId}
POST /glossary/exceptions/{exceptionId}/deactivate
POST /glossary/test-match
GET  /glossary/import/template
POST /glossary/import/preview
POST /glossary/import/confirm
GET  /glossary/export
POST /glossary/validation/jobs
GET  /glossary/validation/jobs
GET  /glossary/validation/jobs/{jobId}
POST /glossary/validation/jobs/{jobId}/cancel
GET  /glossary/validation/runs/{runId}
GET  /glossary/validation/runs/{runId}/summary
GET  /glossary/validation/runs/{runId}/matches
GET  /glossary/validation/runs/{runId}/findings
GET  /glossary/validation/runs/{runId}/export
POST /glossary/validation/runs/{runId}/revalidate
GET  /document-files/{fileId}/glossary-validation
GET  /document-files/{fileId}/glossary-history

POST /revision-comparisons/jobs
GET  /revision-comparisons/jobs
GET  /revision-comparisons/jobs/{jobId}
POST /revision-comparisons/jobs/{jobId}/cancel
GET  /revision-comparisons/{comparisonId}
GET  /revision-comparisons/{comparisonId}/summary
GET  /revision-comparisons/{comparisonId}/changes
GET  /revision-comparisons/{comparisonId}/sections
GET  /revision-comparisons/{comparisonId}/languages
GET  /revision-comparisons/{comparisonId}/findings
GET  /revision-comparisons/{comparisonId}/export
GET  /documents/{documentId}/revision-comparisons

POST /reports/generate
GET  /reports/jobs
GET  /reports/jobs/{jobId}
GET  /reports/snapshots
GET  /reports/snapshots/{snapshotId}
GET  /reports/snapshots/{snapshotId}/download
POST /reports/snapshots/{snapshotId}/delete
GET  /reports/schedules
POST /reports/schedules
PUT  /reports/schedules/{scheduleId}
POST /reports/schedules/{scheduleId}/run
POST /reports/schedules/{scheduleId}/disable
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

## Migration

Phase 9 is introduced by Alembic revision `20260726_0009`, which follows
`20260726_0008`.

```bash
cd backend
alembic upgrade head
alembic downgrade 20260726_0008
```

New tables are:

```text
similarity_jobs
similarity_runs
translation_similarity_results
section_similarity_summaries
glossary_profiles
glossary_terms
glossary_translations
glossary_term_variants
glossary_exceptions
glossary_validation_runs
glossary_matches
revision_comparison_jobs
revision_comparisons
revision_changes
report_snapshots
report_schedules
```

The migration adds latest similarity/glossary run references to
`document_files`, source-run references to `validation_findings`, and the
Phase 9 quality mode/weight fields to `validation_rules`. Foreign keys,
department/query indexes, uniqueness constraints, score/confidence ranges,
nonnegative counters, and bounded status/configuration constraints are applied
at the database layer.

## Synthetic fixtures and tests

Generate the 16 deterministic, non-company DOCX/XLSX fixtures:

```bash
cd backend
python scripts/generate_phase9_sample_documents.py
```

They are written under `sample-documents/similarity`,
`sample-documents/glossary`, and `sample-documents/revisions`. OOXML metadata
and ZIP timestamps are normalized, so repeated generation produces identical
hashes.

Focused fixture verification:

```bash
cd backend
python -m pytest app/tests/test_phase9_sample_documents.py
```

The test verifies the exact inventory, deterministic hashes, readable OOXML,
bounded file sizes, canonical glossary import headers, and named mismatch and
revision-change evidence.

## Troubleshooting

- **Model not found:** run the explicit model installer, then
  `--offline-verify`; confirm the same `./models` volume is mounted in the
  similarity worker.
- **Worker out of memory:** keep similarity/reporting concurrency low, reduce
  batch size or configured row/block limits, and inspect container limits.
- **Low score on short text:** inspect `NOT_EVALUATED`, minimum-character,
  group/language confidence, and chunk-completeness evidence before changing a
  threshold.
- **Glossary term not detected:** check profile resolution, language,
  active/preferred flags, case/whole-word settings, and variants.
- **Chinese boundary issue:** use explicit Chinese terms/variants and inspect
  substring matches; do not rely on whitespace boundaries.
- **Low revision alignment confidence:** inspect canonical section, source
  reference, entity type, normalized text, and position signals.
- **PDF report failed:** check ReportLab/font availability and
  `REPORT_PDF_MAX_TABLE_ROWS`; retry after the failed job becomes terminal.
- **Snapshot expired:** generate a fresh snapshot; expired private artifacts
  are not served.
- **Job stuck queued:** verify Redis, the named queue, the corresponding worker
  health, and the post-commit dispatch logs before rerunning.

## Explicit non-goals

- no automatic translation;
- no source-document modification;
- no cloud AI or external translation API;
- no legal-correctness claim from similarity;
- no automatic Critical severity from low similarity;
- no automatic finding resolution;
- no public report/model/storage paths;
- no scheduled email delivery;
- no SharePoint synchronization; and
- no Phase 10 functionality.
