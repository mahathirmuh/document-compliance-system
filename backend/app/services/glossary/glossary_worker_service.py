"""Database orchestration for the dedicated local glossary worker."""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuditAction
from app.database.session import AsyncSessionFactory
from app.models.compliance_run import ComplianceRun
from app.models.detected_section import DetectedSection
from app.models.document import Document
from app.models.document_file import DocumentFileStatus
from app.models.glossary_enums import (
    TERMINAL_GLOSSARY_VALIDATION_STATUSES,
    GlossaryLanguageCode,
    GlossarySourceType,
    GlossaryTermSeverity,
    GlossaryTermType,
    GlossaryValidationStatus,
    GlossaryVariantType,
)
from app.models.glossary_term import GlossaryTerm
from app.models.glossary_term_variant import GlossaryTermVariant
from app.models.glossary_translation import GlossaryTranslation
from app.models.glossary_validation_run import GlossaryValidationRun
from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember
from app.repositories.audit_log import AuditLogRepository
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.glossary_exception_repository import (
    GlossaryExceptionRepository,
)
from app.repositories.glossary_validation_repository import (
    GlossaryValidationRepository,
)
from app.repositories.language_block_result_repository import (
    LanguageBlockResultRepository,
)
from app.services.glossary.contracts import (
    GlossaryTextBlock,
    GlossaryValidationScope,
)
from app.services.glossary.glossary_persistence_service import (
    GlossaryPersistenceService,
)
from app.services.glossary.glossary_validation_service import (
    GlossaryValidationService,
)
from app.services.quality_score_service import QualityScoreService
from app.utils.datetime import utc_now

logger = logging.getLogger(__name__)

_LOCAL_LEASE_GUARD = threading.Lock()
_LOCAL_LEASES: set[UUID] = set()


class GlossaryWorkerError(RuntimeError):
    """Controlled non-retryable worker failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TransientGlossaryWorkerError(RuntimeError):
    """Infrastructure failure safe for a bounded Celery retry."""


class GlossaryWorkerService:
    """Load retained text, validate locally, and persist atomically."""

    def __init__(
        self,
        settings,
        *,
        session_factory=AsyncSessionFactory,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.maximum_blocks = int(
            getattr(settings, "glossary_validation_max_blocks", 2_000_000)
        )
        self.batch_size = int(
            getattr(settings, "glossary_db_batch_size", 1000)
        )
        self.validation = GlossaryValidationService()

    async def process_job(
        self,
        run_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> GlossaryValidationStatus:
        try:
            async with self._execution_lease(run_id) as acquired:
                if not acquired:
                    async with self.session_factory() as session:
                        run = await GlossaryValidationRepository(
                            session
                        ).get_by_id(run_id)
                        return (
                            run.status
                            if run is not None
                            else GlossaryValidationStatus.FAILED
                        )
                return await self._process(
                    run_id,
                    worker_reference=worker_reference,
                    attempt_number=attempt_number,
                )
        except TransientGlossaryWorkerError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            raise TransientGlossaryWorkerError(
                "Glossary worker data source is temporarily unavailable."
            ) from exc

    async def _process(
        self,
        run_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> GlossaryValidationStatus:
        try:
            async with self.session_factory() as session:
                run, acquired = await self._start(
                    session,
                    run_id,
                    worker_reference=worker_reference,
                    attempt_number=attempt_number,
                )
                if run is None:
                    return GlossaryValidationStatus.FAILED
                if run.status in TERMINAL_GLOSSARY_VALIDATION_STATUSES:
                    return run.status
                if run.status is GlossaryValidationStatus.CANCEL_REQUESTED:
                    return await self._cancel(session, run)
                if not acquired:
                    return run.status

                blocks = await self._load_blocks(session, run)
                await self._set_progress(
                    session,
                    run,
                    status=GlossaryValidationStatus.MATCHING_TERMS,
                    progress=25,
                    stage="Matching glossary terms",
                )
                if await self._cancel_requested(session, run.id):
                    return await self._cancel_locked(session, run.id)
                terms = self._terms_from_snapshots(
                    run.profile_snapshots_json
                )
                document = await session.get(Document, run.document_id)
                if document is None:
                    raise GlossaryWorkerError(
                        "GLOSSARY_DOCUMENT_NOT_FOUND",
                        "The source document is no longer available.",
                    )
                exceptions = await GlossaryExceptionRepository(
                    session
                ).list_for_terms([item.id for item in terms])
                await self._set_progress(
                    session,
                    run,
                    status=GlossaryValidationStatus.VALIDATING_TERMS,
                    progress=65,
                    stage="Validating glossary rules",
                )
                result = self.validation.validate(
                    blocks=blocks,
                    terms=terms,
                    exceptions=exceptions,
                    scope=GlossaryValidationScope(
                        department_id=document.department_id,
                        document_type_id=document.document_type_id,
                        document_id=run.document_id,
                        document_revision_id=run.document_revision_id,
                        document_file_id=run.document_file_id,
                    ),
                )
                quality = QualityScoreService.glossary_quality(
                    total_terms=result.total_terms,
                    forbidden_terms=result.forbidden_term_matches,
                    missing_translations=(
                        result.missing_required_translations
                    ),
                    inconsistent_terms=result.inconsistent_terms,
                )
                rule_snapshot: dict[str, object] = {}
                if run.compliance_run_id is not None:
                    compliance = await session.get(
                        ComplianceRun,
                        run.compliance_run_id,
                    )
                    if compliance is not None:
                        rule_snapshot = dict(
                            compliance.rule_snapshot_json or {}
                        )
                result = replace(
                    result,
                    metrics={
                        **result.metrics,
                        "glossaryQualityScore": quality.score,
                        "glossaryQualityStatus": quality.status.value,
                        "qualityConfigurationSnapshot": (
                            QualityScoreService
                            .configuration_from_rule_snapshot(
                                rule_snapshot
                            )
                        ),
                    },
                )
                await self._set_progress(
                    session,
                    run,
                    status=GlossaryValidationStatus.GENERATING_FINDINGS,
                    progress=85,
                    stage="Generating glossary findings",
                )
                if await self._cancel_requested(session, run.id):
                    return await self._cancel_locked(session, run.id)
                await self._set_progress(
                    session,
                    run,
                    status=GlossaryValidationStatus.PERSISTING,
                    progress=95,
                    stage="Persisting glossary result",
                )
                locked = await GlossaryValidationRepository(
                    session
                ).get_by_id(run.id, for_update=True)
                if locked is None:
                    raise GlossaryWorkerError(
                        "GLOSSARY_RUN_NOT_FOUND",
                        "Glossary validation no longer exists.",
                    )
                if locked.status in TERMINAL_GLOSSARY_VALIDATION_STATUSES:
                    return locked.status
                if (
                    locked.status
                    is GlossaryValidationStatus.CANCEL_REQUESTED
                ):
                    return await self._cancel(session, locked)
                details = dict(locked.error_details_json or {})
                if (
                    details.get("workerReference") != worker_reference
                    or details.get("workerAttempt") != attempt_number
                ):
                    return locked.status
                await self._ensure_source_current(session, locked)
                _, findings = await GlossaryPersistenceService(
                    session,
                    batch_size=self.batch_size,
                ).persist(locked, result)
                await AuditLogRepository(session).create(
                    user_id=locked.requested_by,
                    action=AuditAction.COMPLETE_GLOSSARY_VALIDATION,
                    entity_type="GlossaryValidationRun",
                    entity_id=locked.id,
                    description="Glossary validation completed.",
                    new_values={
                        "documentFileId": str(locked.document_file_id),
                        "sourceContentHash": locked.source_content_hash,
                        "totalMatches": len(result.matches),
                        "totalFindings": len(findings),
                        "status": locked.status.value,
                    },
                )
                await session.commit()
                return locked.status
        except GlossaryWorkerError as exc:
            await self.fail_job(
                run_id,
                error_code=exc.code,
                error_message=str(exc),
            )
            return GlossaryValidationStatus.FAILED
        except (DBAPIError, OSError) as exc:
            raise TransientGlossaryWorkerError(
                "Glossary data source is temporarily unavailable."
            ) from exc
        except SQLAlchemyError:
            logger.exception("Glossary persistence failed for %s.", run_id)
            await self.fail_job(
                run_id,
                error_code="GLOSSARY_PERSISTENCE_FAILED",
                error_message=(
                    "Glossary validation result could not be persisted."
                ),
            )
            return GlossaryValidationStatus.FAILED
        except SoftTimeLimitExceeded:
            raise
        except (TypeError, ValueError):
            logger.exception("Glossary validation failed for %s.", run_id)
            await self.fail_job(
                run_id,
                error_code="GLOSSARY_VALIDATION_FAILED",
                error_message="Glossary validation could not be completed.",
            )
            return GlossaryValidationStatus.FAILED

    async def fail_job(
        self,
        run_id: UUID,
        *,
        error_code: str,
        error_message: str,
    ) -> GlossaryValidationStatus:
        async with self.session_factory() as session:
            run = await GlossaryValidationRepository(session).get_by_id(
                run_id,
                for_update=True,
            )
            if run is None:
                return GlossaryValidationStatus.FAILED
            if run.status in TERMINAL_GLOSSARY_VALIDATION_STATUSES:
                return run.status
            if run.status is GlossaryValidationStatus.CANCEL_REQUESTED:
                return await self._cancel(session, run)
            run.status = GlossaryValidationStatus.FAILED
            run.current_stage = "Failed"
            run.error_code = error_code[:100]
            run.error_message = error_message[:4000]
            run.failed_at = utc_now()
            await AuditLogRepository(session).create(
                user_id=run.requested_by,
                action=AuditAction.FAIL_GLOSSARY_VALIDATION,
                entity_type="GlossaryValidationRun",
                entity_id=run.id,
                description="Glossary validation failed.",
                new_values={"errorCode": run.error_code},
            )
            await session.commit()
            return run.status

    async def _start(
        self,
        session: AsyncSession,
        run_id: UUID,
        *,
        worker_reference: str,
        attempt_number: int,
    ) -> tuple[GlossaryValidationRun | None, bool]:
        run = await GlossaryValidationRepository(session).get_by_id(
            run_id,
            for_update=True,
        )
        if run is None or run.status in TERMINAL_GLOSSARY_VALIDATION_STATUSES:
            return run, False
        if run.status is GlossaryValidationStatus.CANCEL_REQUESTED:
            return run, False
        details = dict(run.error_details_json or {})
        same_worker_retry = (
            details.get("workerReference") == worker_reference
            and attempt_number > int(details.get("workerAttempt", 0))
        )
        if (
            run.status is not GlossaryValidationStatus.QUEUED
            and not same_worker_retry
        ):
            return run, False
        run.status = GlossaryValidationStatus.LOADING_CONTEXT
        run.progress = max(run.progress, 5)
        run.current_stage = "Loading retained glossary context"
        run.started_at = run.started_at or utc_now()
        details["workerReference"] = worker_reference
        details["workerAttempt"] = attempt_number
        run.error_details_json = details
        await session.commit()
        return run, True

    async def _load_blocks(
        self,
        session: AsyncSession,
        run: GlossaryValidationRun,
    ) -> list[GlossaryTextBlock]:
        rows = await LanguageBlockResultRepository(
            session
        ).list_compliance_sources(
            run.language_detection_run_id,
            limit=self.maximum_blocks + 1,
        )
        if len(rows) > self.maximum_blocks:
            raise GlossaryWorkerError(
                "GLOSSARY_BLOCK_LIMIT_EXCEEDED",
                "Glossary source exceeds the configured block limit.",
            )
        group_mapping = await self._group_mapping(session, run)
        blocks: list[GlossaryTextBlock] = []
        for row in rows:
            if (
                row.eligibility_status != "ELIGIBLE"
                or row.language_code not in {"id", "en", "zh"}
                or not row.text
                or row.id is None
            ):
                continue
            source_type = str(
                row.metadata.get("sourceType", "NATIVE_EXTRACTION")
            )
            is_ocr = source_type == GlossarySourceType.OCR.value
            mapping = group_mapping.get(
                (
                    source_type,
                    row.id,
                ),
                {},
            )
            blocks.append(
                GlossaryTextBlock(
                    text=row.text,
                    language_code=row.language_code,
                    source_type=source_type,
                    source_reference=row.source_reference,
                    extracted_block_id=None if is_ocr else row.id,
                    ocr_block_id=row.id if is_ocr else None,
                    container_id=row.container_id,
                    detected_section_id=mapping.get("sectionId"),
                    section_definition_id=mapping.get(
                        "sectionDefinitionId"
                    ),
                    translation_group_id=mapping.get("groupId"),
                    confidence=float(row.language_confidence),
                )
            )
        if not blocks:
            raise GlossaryWorkerError(
                "GLOSSARY_SOURCE_EMPTY",
                "No eligible ID, EN, or ZH extracted text is available.",
            )
        return blocks

    @staticmethod
    async def _group_mapping(
        session: AsyncSession,
        run: GlossaryValidationRun,
    ) -> dict[tuple[str, UUID], dict[str, UUID | None]]:
        if run.compliance_run_id is None:
            return {}
        rows = (
            await session.execute(
                select(
                    TranslationGroupMember,
                    TranslationGroup,
                    DetectedSection,
                )
                .join(
                    TranslationGroup,
                    TranslationGroup.id
                    == TranslationGroupMember.translation_group_id,
                )
                .outerjoin(
                    DetectedSection,
                    DetectedSection.id
                    == TranslationGroup.detected_section_id,
                )
                .where(
                    TranslationGroup.compliance_run_id
                    == run.compliance_run_id
                )
            )
        ).all()
        result: dict[tuple[str, UUID], dict[str, UUID | None]] = {}
        for member, group, section in rows:
            block_id = member.extracted_block_id or member.ocr_block_id
            if block_id is None:
                continue
            result[(member.source_type, block_id)] = {
                "groupId": group.id,
                "sectionId": group.detected_section_id,
                "sectionDefinitionId": (
                    section.section_definition_id
                    if section is not None
                    else None
                ),
            }
        return result

    @staticmethod
    def _terms_from_snapshots(
        snapshots: list[dict[str, object]],
    ) -> list[GlossaryTerm]:
        terms: list[GlossaryTerm] = []
        for profile in snapshots:
            profile_id = UUID(str(profile["id"]))
            raw_terms = profile.get("terms", [])
            if not isinstance(raw_terms, list):
                continue
            for raw in raw_terms:
                if not isinstance(raw, dict):
                    continue
                term = GlossaryTerm(
                    id=UUID(str(raw["id"])),
                    glossary_profile_id=profile_id,
                    term_code=str(raw["termCode"]),
                    concept_name=str(raw["conceptName"]),
                    term_type=GlossaryTermType(str(raw["termType"])),
                    severity=GlossaryTermSeverity(str(raw["severity"])),
                    is_case_sensitive=bool(raw["isCaseSensitive"]),
                    match_whole_word=bool(raw["matchWholeWord"]),
                    allow_inflection=bool(raw["allowInflection"]),
                    is_regex=bool(raw["isRegex"]),
                    is_active=True,
                    created_by=None,
                    updated_by=None,
                )
                translations: list[GlossaryTranslation] = []
                raw_translations = raw.get("translations", [])
                if not isinstance(raw_translations, list):
                    raw_translations = []
                for raw_translation in raw_translations:
                    if not isinstance(raw_translation, dict):
                        continue
                    translation = GlossaryTranslation(
                        id=UUID(str(raw_translation["id"])),
                        glossary_term_id=term.id,
                        language_code=GlossaryLanguageCode(
                            str(raw_translation["languageCode"])
                        ),
                        term_text=str(raw_translation["termText"]),
                        normalised_term=str(
                            raw_translation["normalisedTerm"]
                        ),
                        is_preferred=bool(
                            raw_translation["isPreferred"]
                        ),
                        is_forbidden=bool(
                            raw_translation["isForbidden"]
                        ),
                        is_required=bool(
                            raw_translation["isRequired"]
                        ),
                        priority=int(raw_translation["priority"]),
                        is_active=True,
                    )
                    variants: list[GlossaryTermVariant] = []
                    raw_variants = raw_translation.get("variants", [])
                    if not isinstance(raw_variants, list):
                        raw_variants = []
                    for raw_variant in raw_variants:
                        if not isinstance(raw_variant, dict):
                            continue
                        variants.append(
                            GlossaryTermVariant(
                                id=UUID(str(raw_variant["id"])),
                                glossary_translation_id=translation.id,
                                variant_text=str(
                                    raw_variant["variantText"]
                                ),
                                normalised_variant=str(
                                    raw_variant["normalisedVariant"]
                                ),
                                variant_type=GlossaryVariantType(
                                    str(raw_variant["variantType"])
                                ),
                                is_allowed=bool(
                                    raw_variant["isAllowed"]
                                ),
                                is_active=True,
                            )
                        )
                    translation.variants = variants
                    translations.append(translation)
                term.translations = translations
                terms.append(term)
        return terms

    async def _ensure_source_current(
        self,
        session: AsyncSession,
        run: GlossaryValidationRun,
    ) -> None:
        document_file = await DocumentFileRepository(session).get_by_id(
            run.document_file_id,
            for_update=True,
        )
        if (
            document_file is None
            or document_file.file_status is not DocumentFileStatus.AVAILABLE
            or not document_file.is_current
            or document_file.deleted_at is not None
            or document_file.document.is_archived
            or document_file.latest_language_detection_run_id
            != run.language_detection_run_id
        ):
            raise GlossaryWorkerError(
                "GLOSSARY_SOURCE_CHANGED",
                "Glossary source changed before result persistence.",
            )

    async def _set_progress(
        self,
        session: AsyncSession,
        run: GlossaryValidationRun,
        *,
        status: GlossaryValidationStatus,
        progress: int,
        stage: str,
    ) -> None:
        run.status = status
        run.progress = max(run.progress, progress)
        run.current_stage = stage
        await session.commit()

    @staticmethod
    async def _cancel_requested(
        session: AsyncSession,
        run_id: UUID,
    ) -> bool:
        status = await session.scalar(
            select(GlossaryValidationRun.status)
            .where(GlossaryValidationRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        return status is GlossaryValidationStatus.CANCEL_REQUESTED

    async def _cancel_locked(
        self,
        session: AsyncSession,
        run_id: UUID,
    ) -> GlossaryValidationStatus:
        run = await GlossaryValidationRepository(session).get_by_id(
            run_id,
            for_update=True,
        )
        if run is None:
            return GlossaryValidationStatus.CANCELLED
        return await self._cancel(session, run)

    @staticmethod
    async def _cancel(
        session: AsyncSession,
        run: GlossaryValidationRun,
    ) -> GlossaryValidationStatus:
        run.status = GlossaryValidationStatus.CANCELLED
        run.current_stage = "Cancelled"
        run.cancelled_at = utc_now()
        await session.commit()
        return run.status

    @asynccontextmanager
    async def _execution_lease(
        self,
        run_id: UUID,
    ) -> AsyncIterator[bool]:
        with _LOCAL_LEASE_GUARD:
            acquired = run_id not in _LOCAL_LEASES
            if acquired:
                _LOCAL_LEASES.add(run_id)
        try:
            yield acquired
        finally:
            if acquired:
                with _LOCAL_LEASE_GUARD:
                    _LOCAL_LEASES.discard(run_id)
