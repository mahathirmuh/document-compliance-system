"""Application-timezone boundaries for timestamp-backed date filters."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def created_at_utc_bounds(
    created_from: date | None,
    created_to: date | None,
    timezone_name: str,
) -> tuple[datetime | None, datetime | None]:
    """Return inclusive start and exclusive end UTC timestamps."""
    timezone = ZoneInfo(timezone_name)
    start = (
        datetime.combine(
            created_from,
            time.min,
            tzinfo=timezone,
        ).astimezone(UTC)
        if created_from is not None
        else None
    )
    end: datetime | None = None
    if created_to is not None:
        try:
            day_after = created_to + timedelta(days=1)
        except OverflowError:
            day_after = None
        if day_after is not None:
            end = datetime.combine(
                day_after,
                time.min,
                tzinfo=timezone,
            ).astimezone(UTC)
    return start, end
