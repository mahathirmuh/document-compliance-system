"""Adapt retained Phase 8 translation groups to similarity DTOs."""

from __future__ import annotations

from app.models.translation_group import TranslationGroup
from app.models.translation_group_member import TranslationGroupMember
from app.schemas.similarity_internal import (
    SimilarityGroupData,
    SimilarityMemberData,
)


class TranslationAlignmentService:
    def from_models(
        self,
        groups: list[TranslationGroup],
    ) -> list[SimilarityGroupData]:
        return [
            SimilarityGroupData(
                id=group.id,
                detected_section_id=group.detected_section_id,
                canonical_section_code=(
                    group.detected_section.canonical_code
                    if group.detected_section is not None
                    else None
                ),
                container_id=group.container_id,
                source_reference=group.source_reference,
                group_index=group.group_index,
                group_type=group.group_type.value,
                confidence=float(group.confidence),
                members=[
                    SimilarityMemberData(
                        id=member.id,
                        language_code=member.language_code,
                        text=self._source_text(member),
                        confidence=float(member.confidence),
                        block_order=member.block_order,
                        source_reference=group.source_reference,
                        source_type=member.source_type,
                        metadata={
                            **dict(member.position_json or {}),
                            "ocrConfidence": (
                                float(member.ocr_block.confidence)
                                if member.ocr_block is not None
                                else None
                            ),
                            "snapshotCharacterCount": len(
                                member.text_snapshot
                            ),
                        },
                    )
                    for member in group.members
                ],
                metrics=dict(group.metrics_json or {}),
            )
            for group in groups
        ]

    @staticmethod
    def _source_text(member: TranslationGroupMember) -> str:
        if member.ocr_block is not None:
            return (
                member.ocr_block.normalised_text
                or member.ocr_block.text
                or member.text_snapshot
            )
        if member.extracted_block is not None:
            return (
                member.extracted_block.normalised_text
                or member.extracted_block.text
                or member.text_snapshot
            )
        return member.text_snapshot
