"""Layered filename, register, and duplicate identification."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.core.exceptions import ApplicationError, AuthorizationError
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_revision import DocumentRevision
from app.models.upload_session_item import (
    UploadIdentificationStatus,
    UploadProposedAction,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_file_repository import DocumentFileRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_revision_repository import (
    DocumentRevisionRepository,
)
from app.repositories.document_type_repository import DocumentTypeRepository
from app.schemas.document_upload import (
    FileDuplicateWarning,
    ParsedDocumentMetadata,
)
from app.services.documents.base import DocumentServiceBase
from app.services.documents.document_code_service import (
    DocumentCodeError,
    DocumentCodeService,
    ParsedDocumentCode,
)
from app.services.documents.document_service import DocumentService


@dataclass(slots=True)
class FileIdentificationOutcome:
    identification_status: UploadIdentificationStatus
    proposed_action: UploadProposedAction
    parsed_metadata: ParsedDocumentMetadata | None = None
    matched_document: Document | None = None
    matched_revision: DocumentRevision | None = None
    duplicate_warning: FileDuplicateWarning | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class FileIdentificationService(DocumentServiceBase):
    """Identify a validated staged file without mutating the register."""

    def __init__(self, session, settings, user, metadata) -> None:
        super().__init__(session, user, metadata)
        self.settings = settings
        self.documents = DocumentRepository(session)
        self.revisions = DocumentRevisionRepository(session)
        self.files = DocumentFileRepository(session)
        self.department_repository = DepartmentRepository(session)
        self.type_repository = DocumentTypeRepository(session)
        self.codes = DocumentCodeService()

    async def identify(
        self,
        *,
        filename: str,
        sha256_hash: str,
        file_size: int,
        document_id: UUID | None = None,
        revision_id: UUID | None = None,
    ) -> FileIdentificationOutcome:
        if revision_id is not None and document_id is None:
            raise self._identification_error(
                "documentId is required when revisionId is provided."
            )
        if document_id is not None:
            outcome = await self._identify_explicit_target(
                document_id,
                revision_id,
            )
        else:
            outcome = await self._identify_filename(filename)
        if not self.settings.enable_duplicate_file_hash_check:
            return outcome
        duplicates = await self.files.find_by_hash(sha256_hash, file_size)
        return self._apply_duplicate_policy(outcome, duplicates)

    async def _identify_explicit_target(
        self,
        document_id: UUID,
        revision_id: UUID | None,
    ) -> FileIdentificationOutcome:
        document = await self.documents.get_detail(document_id)
        if document is None:
            raise self._identification_error("Document was not found.")
        self.policy.ensure_document_access(document)
        if revision_id is None:
            return FileIdentificationOutcome(
                identification_status=(
                    UploadIdentificationStatus.PARTIALLY_IDENTIFIED
                ),
                proposed_action=UploadProposedAction.MANUAL_REVIEW,
                matched_document=document,
                warnings=[
                    "Select a revision before confirming the upload."
                ],
            )
        revision = await self.revisions.get_by_id(
            revision_id,
            document_id=document.id,
        )
        if revision is None:
            raise self._identification_error(
                "Document revision was not found."
            )
        current = await self.files.get_current_by_revision(revision.id)
        return FileIdentificationOutcome(
            identification_status=UploadIdentificationStatus.IDENTIFIED,
            proposed_action=(
                UploadProposedAction.REPLACE_CURRENT_FILE
                if current is not None
                else UploadProposedAction.ATTACH_TO_EXISTING_REVISION
            ),
            parsed_metadata=self._metadata_from_entities(
                document,
                revision,
            ),
            matched_document=document,
            matched_revision=revision,
            warnings=(
                ["The target revision already has a current file."]
                if current is not None
                else []
            ),
        )

    async def _identify_filename(
        self,
        filename: str,
    ) -> FileIdentificationOutcome:
        parser = DocumentService(
            self.session,
            self.settings,
            self.user,
            self.metadata,
        )
        try:
            parsed = await parser.parse_code(filename)
        except ApplicationError as exc:
            return await self._partial_identification(filename, exc)
        metadata = ParsedDocumentMetadata(
            company_code=parsed.company_code,
            department_code=parsed.department.code,
            section_code=(
                parsed.section.code if parsed.section is not None else None
            ),
            document_type_code=parsed.document_type.code,
            document_number=parsed.document_number,
            title=parsed.document_title,
            revision_code=parsed.revision_code,
            base_document_code=parsed.base_document_code,
            full_document_code=parsed.full_document_code,
        )
        if parsed.full_document_code is not None:
            revision = await self.revisions.get_by_full_code(
                parsed.full_document_code
            )
            if revision is not None:
                document = await self.documents.get_detail(
                    revision.document_id
                )
                assert document is not None
                try:
                    self.policy.ensure_document_access(document)
                except AuthorizationError:
                    return FileIdentificationOutcome(
                        identification_status=(
                            UploadIdentificationStatus.PARTIALLY_IDENTIFIED
                        ),
                        proposed_action=UploadProposedAction.MANUAL_REVIEW,
                        parsed_metadata=metadata,
                        warnings=[
                            (
                                "A matching document exists outside your "
                                "department scope."
                            )
                        ],
                    )
                current = await self.files.get_current_by_revision(
                    revision.id
                )
                return FileIdentificationOutcome(
                    identification_status=(
                        UploadIdentificationStatus.IDENTIFIED
                    ),
                    proposed_action=(
                        UploadProposedAction.REPLACE_CURRENT_FILE
                        if current is not None
                        else (
                            UploadProposedAction
                            .ATTACH_TO_EXISTING_REVISION
                        )
                    ),
                    parsed_metadata=metadata,
                    matched_document=document,
                    matched_revision=revision,
                    warnings=[
                        *parsed.warnings,
                        *(
                            [
                                (
                                    "The matching revision already has a "
                                    "current file."
                                )
                            ]
                            if current is not None
                            else []
                        ),
                    ],
                )
        document = await self.documents.get_by_base_code(
            parsed.base_document_code
        )
        if document is not None:
            try:
                self.policy.ensure_document_access(document)
            except AuthorizationError:
                return FileIdentificationOutcome(
                    identification_status=(
                        UploadIdentificationStatus.PARTIALLY_IDENTIFIED
                    ),
                    proposed_action=UploadProposedAction.MANUAL_REVIEW,
                    parsed_metadata=metadata,
                    warnings=[
                        (
                            "A matching document exists outside your "
                            "department scope."
                        )
                    ],
                )
            if parsed.revision_code is None:
                return FileIdentificationOutcome(
                    identification_status=(
                        UploadIdentificationStatus.PARTIALLY_IDENTIFIED
                    ),
                    proposed_action=UploadProposedAction.MANUAL_REVIEW,
                    parsed_metadata=metadata,
                    matched_document=document,
                    warnings=[
                        *parsed.warnings,
                        "The filename does not contain a revision code.",
                    ],
                )
            return FileIdentificationOutcome(
                identification_status=UploadIdentificationStatus.IDENTIFIED,
                proposed_action=UploadProposedAction.ADD_NEW_REVISION,
                parsed_metadata=metadata,
                matched_document=document,
                warnings=list(parsed.warnings),
            )
        if parsed.revision_code is None:
            return FileIdentificationOutcome(
                identification_status=(
                    UploadIdentificationStatus.PARTIALLY_IDENTIFIED
                ),
                proposed_action=UploadProposedAction.MANUAL_REVIEW,
                parsed_metadata=metadata,
                warnings=[
                    *parsed.warnings,
                    (
                        "A revision code and document title are required "
                        "before a new document can be created."
                    ),
                ],
            )
        return FileIdentificationOutcome(
            identification_status=UploadIdentificationStatus.IDENTIFIED,
            proposed_action=(
                UploadProposedAction.CREATE_DOCUMENT_AND_REVISION
            ),
            parsed_metadata=metadata,
            warnings=[
                *parsed.warnings,
                *(
                    ["Enter a document title before confirming."]
                    if metadata.title is None
                    else []
                ),
            ],
        )

    async def _partial_identification(
        self,
        filename: str,
        error: ApplicationError,
    ) -> FileIdentificationOutcome:
        errors = (
            [detail.message for detail in error.errors]
            if error.errors
            else [error.message]
        )
        candidates: list[ParsedDocumentCode] = []
        for has_section in (True, False):
            try:
                candidates.extend(
                    self.codes.parse_document_code_candidates(
                        filename,
                        has_section=has_section,
                    )
                )
            except DocumentCodeError:
                continue
        best: ParsedDocumentCode | None = None
        for candidate in candidates:
            department = await self.department_repository.get_by_code(
                candidate.department_code
            )
            document_type = await self.type_repository.get_by_code(
                candidate.document_type_code
            )
            if department is not None or document_type is not None:
                best = candidate
                if department is not None and document_type is not None:
                    break
        if best is None:
            return FileIdentificationOutcome(
                identification_status=(
                    UploadIdentificationStatus.NOT_IDENTIFIED
                ),
                proposed_action=UploadProposedAction.MANUAL_REVIEW,
                errors=errors,
            )
        return FileIdentificationOutcome(
            identification_status=(
                UploadIdentificationStatus.PARTIALLY_IDENTIFIED
            ),
            proposed_action=UploadProposedAction.MANUAL_REVIEW,
            parsed_metadata=ParsedDocumentMetadata(
                company_code=best.company_code,
                department_code=best.department_code,
                section_code=best.section_code,
                document_type_code=best.document_type_code,
                document_number=best.document_number,
                title=best.document_title,
                revision_code=best.revision_code,
                base_document_code=best.base_document_code,
                full_document_code=best.full_document_code,
            ),
            errors=errors,
        )

    def _apply_duplicate_policy(
        self,
        outcome: FileIdentificationOutcome,
        duplicates: list[DocumentFile],
    ) -> FileIdentificationOutcome:
        if not duplicates:
            return outcome
        same_revision = (
            outcome.matched_revision is not None
            and any(
                item.document_revision_id == outcome.matched_revision.id
                for item in duplicates
            )
        )
        visible_duplicate = next(
            (
                item
                for item in duplicates
                if self.policy.view_all_departments
                or item.document.department_id == self.user.department_id
            ),
            None,
        )
        warning = FileDuplicateWarning(
            same_revision=same_revision,
            document_id=(
                visible_duplicate.document_id
                if visible_duplicate is not None
                else None
            ),
            revision_id=(
                visible_duplicate.document_revision_id
                if visible_duplicate is not None
                else None
            ),
            base_document_code=(
                visible_duplicate.document.base_document_code
                if visible_duplicate is not None
                else None
            ),
        )
        outcome.duplicate_warning = warning
        outcome.identification_status = (
            UploadIdentificationStatus.DUPLICATE_FILE
        )
        outcome.warnings.append(warning.message)
        if same_revision:
            outcome.proposed_action = UploadProposedAction.SKIP
        elif (
            outcome.matched_document is None
            or any(
                item.document_id != outcome.matched_document.id
                for item in duplicates
            )
        ):
            outcome.proposed_action = UploadProposedAction.MANUAL_REVIEW
        return outcome

    @staticmethod
    def _metadata_from_entities(
        document: Document,
        revision: DocumentRevision,
    ) -> ParsedDocumentMetadata:
        return ParsedDocumentMetadata(
            company_code=document.company_code,
            department_code=document.department.code,
            section_code=(
                document.section.code
                if document.section is not None
                else None
            ),
            document_type_code=document.document_type.code,
            document_number=document.document_number,
            title=document.title,
            revision_code=revision.revision_code,
            base_document_code=document.base_document_code,
            full_document_code=revision.full_document_code,
        )

    @staticmethod
    def _identification_error(message: str) -> ApplicationError:
        from app.services.documents.base import document_error

        return document_error(message, field="file")
