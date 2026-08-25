from __future__ import annotations

from datetime import datetime, timedelta, timezone

MAX_RANGE = timedelta(minutes=30)
MAX_LOG_RECORDS = 200
MAX_TRACES = 20
DEFAULT_TIMEOUT_SECONDS = 8.0
MAX_RETRIES = 2


class BoundsError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clamp_window(start: datetime, end: datetime, maximum: timedelta = MAX_RANGE) -> tuple[datetime, datetime]:
    if end < start:
        raise BoundsError("end must be after start")
    if end - start > maximum:
        raise BoundsError(f"time range exceeds {maximum.total_seconds()} seconds")
    return start, end


def to_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_unix_nanos(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1_000_000_000)
