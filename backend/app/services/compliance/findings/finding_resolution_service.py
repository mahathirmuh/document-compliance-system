"""Pure finding status-transition and reason/comment validation."""

from __future__ import annotations

from datetime import date

from app.services.compliance._compat import (
    copy_update,
    enum_value,
    read,
)
from app.services.compliance.constants import FindingStatus
from app.services.compliance.findings.finding_factory import (
    sanitize_user_text,
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    FindingStatus.OPEN: frozenset(
        {
            FindingStatus.IN_REVIEW,
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.ACCEPTED_RISK,
        },
    ),
    FindingStatus.IN_REVIEW: frozenset(
        {
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.ACCEPTED_RISK,
            FindingStatus.OPEN,
        },
    ),
    FindingStatus.RESOLVED: frozenset({FindingStatus.REOPENED}),
    FindingStatus.FALSE_POSITIVE: frozenset({FindingStatus.REOPENED}),
    FindingStatus.ACCEPTED_RISK: frozenset({FindingStatus.REOPENED}),
    FindingStatus.REOPENED: frozenset(
        {
            FindingStatus.IN_REVIEW,
            FindingStatus.RESOLVED,
            FindingStatus.FALSE_POSITIVE,
            FindingStatus.ACCEPTED_RISK,
        },
    ),
    FindingStatus.CLOSED: frozenset(),
}


class FindingTransitionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class FindingResolutionService:
    """Validate a workflow action and return an updated in-memory finding."""

    def transition(
        self,
        finding: object,
        target_status: str,
        *,
        actor_id: object | None = None,
        comment: str | None = None,
        reason: str | None = None,
        expiry_date: date | str | None = None,
    ) -> object:
        current = enum_value(read(finding, "status", FindingStatus.OPEN)).upper()
        target = enum_value(target_status).upper()
        if target not in _TRANSITIONS.get(current, frozenset()):
            raise FindingTransitionError(
                "FINDING_INVALID_STATUS_TRANSITION",
                f"Finding cannot transition from {current} to {target}.",
            )
        clean_comment = (
            sanitize_user_text(comment, maximum=4000)
            if comment is not None
            else ""
        )
        clean_reason = (
            sanitize_user_text(reason, maximum=4000)
            if reason is not None
            else ""
        )
        actor = str(actor_id) if actor_id is not None else None
        updates: dict[str, object] = {"status": target}

        if target == FindingStatus.IN_REVIEW:
            if not clean_comment:
                raise FindingTransitionError(
                    "FINDING_REVIEW_COMMENT_REQUIRED",
                    "A review comment is required.",
                )
            updates.update(
                reviewed_by=actor,
                review_comment=clean_comment,
            )
        elif target == FindingStatus.RESOLVED:
            if not clean_comment:
                raise FindingTransitionError(
                    "FINDING_RESOLUTION_COMMENT_REQUIRED",
                    "A resolution comment is required.",
                )
            updates.update(
                resolved_by=actor,
                resolution_comment=clean_comment,
            )
        elif target == FindingStatus.FALSE_POSITIVE:
            if not clean_reason:
                raise FindingTransitionError(
                    "FINDING_FALSE_POSITIVE_REASON_REQUIRED",
                    "A false-positive reason is required.",
                )
            updates.update(
                false_positive_by=actor,
                false_positive_reason=clean_reason,
            )
        elif target == FindingStatus.ACCEPTED_RISK:
            if not clean_reason or expiry_date is None:
                raise FindingTransitionError(
                    "FINDING_ACCEPT_RISK_REASON_REQUIRED",
                    "An accepted-risk reason and expiry date are required.",
                )
            updates.update(
                accepted_risk_reason=clean_reason,
                accepted_risk_expiry=(
                    expiry_date.isoformat()
                    if isinstance(expiry_date, date)
                    else str(expiry_date)
                ),
            )
        elif target == FindingStatus.REOPENED:
            if not clean_reason:
                raise FindingTransitionError(
                    "FINDING_REOPEN_REASON_REQUIRED",
                    "A reopen reason is required.",
                )
            updates["reopen_reason"] = clean_reason
        elif target == FindingStatus.OPEN and current == FindingStatus.IN_REVIEW:
            if not clean_comment:
                raise FindingTransitionError(
                    "FINDING_REVIEW_COMMENT_REQUIRED",
                    "A comment is required when returning a finding to open.",
                )
            updates["review_comment"] = clean_comment
        return copy_update(finding, **updates)

    def review(
        self,
        finding: object,
        *,
        actor_id: object,
        comment: str,
    ) -> object:
        return self.transition(
            finding,
            FindingStatus.IN_REVIEW,
            actor_id=actor_id,
            comment=comment,
        )

    def resolve(
        self,
        finding: object,
        *,
        actor_id: object,
        comment: str,
    ) -> object:
        return self.transition(
            finding,
            FindingStatus.RESOLVED,
            actor_id=actor_id,
            comment=comment,
        )

    def mark_false_positive(
        self,
        finding: object,
        *,
        actor_id: object,
        reason: str,
    ) -> object:
        return self.transition(
            finding,
            FindingStatus.FALSE_POSITIVE,
            actor_id=actor_id,
            reason=reason,
        )

    def accept_risk(
        self,
        finding: object,
        *,
        actor_id: object,
        reason: str,
        expiry_date: date | str,
    ) -> object:
        return self.transition(
            finding,
            FindingStatus.ACCEPTED_RISK,
            actor_id=actor_id,
            reason=reason,
            expiry_date=expiry_date,
        )

    def reopen(
        self,
        finding: object,
        *,
        actor_id: object,
        reason: str,
    ) -> object:
        return self.transition(
            finding,
            FindingStatus.REOPENED,
            actor_id=actor_id,
            reason=reason,
        )

    @staticmethod
    def assign(
        finding: object,
        *,
        assigned_to: object,
    ) -> object:
        if assigned_to is None or not str(assigned_to).strip():
            raise FindingTransitionError(
                "FINDING_ASSIGNMENT_INVALID",
                "A valid assignment target is required.",
            )
        return copy_update(finding, assigned_to=str(assigned_to))


def allowed_transitions(status: str) -> tuple[str, ...]:
    return tuple(sorted(_TRANSITIONS.get(status.upper(), frozenset())))

