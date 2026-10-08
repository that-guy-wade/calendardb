"""UTC timestamps for CalendarDB's time index."""

from datetime import datetime, timezone
import re


def parse_timestamp(value):
    if isinstance(value, str):
        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
        ):
            raise ValueError("Timestamps must be RFC3339 with a timezone")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def format_timestamp(value):
    return parse_timestamp(value).isoformat().replace("+00:00", "Z")


def in_range(timestamp, start, end):
    return (start is None or timestamp >= start) and (end is None or timestamp < end)
