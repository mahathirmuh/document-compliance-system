"""Public structural translation-group response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.models.compliance_enums import TranslationGroupType
from app.schemas.base import ApiSchema
from app.schemas.common import PaginationData


class TranslationGroupMemberResponse(ApiSchema):
    id: UUID
    translation_group_id: UUID
    language_code: str
    source_type: str
    extracted_block_id: UUID | None
    ocr_block_id: UUID | None
    language_block_result_id: UUID | None
    block_order: int = Field(ge=0)
    text_snapshot: str
    confidence: float = Field(ge=0, le=1)
    position: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TranslationGroupResponse(ApiSchema):
    id: UUID
    compliance_run_id: UUID
    container_id: UUID | None
    detected_section_id: UUID | None
    group_index: int = Field(ge=0)
    group_type: TranslationGroupType
    start_block_order: int = Field(ge=0)
    end_block_order: int = Field(ge=0)
    source_reference: str
    expected_languages: list[str]
    detected_languages: list[str]
    language_order: list[str]
    is_complete: bool
    is_order_valid: bool
    confidence: float = Field(ge=0, le=1)
    metrics: dict[str, Any] = Field(default_factory=dict)
    members: list[TranslationGroupMemberResponse] = Field(
        default_factory=list
    )
    finding_count: int = Field(default=0, ge=0)
    created_at: datetime


class TranslationGroupListResponse(
    PaginationData[TranslationGroupResponse]
):
    pass


class TranslationGroupFilter(ApiSchema):
    compliance_run_id: UUID
    container_id: UUID | None = None
    detected_section_id: UUID | None = None
    group_type: TranslationGroupType | None = None
    is_complete: bool | None = None
    is_order_valid: bool | None = None
    minimum_confidence: float | None = Field(default=None, ge=0, le=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
