"""Lossless event descriptions for timestamped records."""

import json

MARKER = "CALENDARDB v1"


def encode(record):
    series = record.get("series") or record.get("name") or record.get("logger") or "record"
    service = record.get("service", "")
    value = record.get("value", record.get("level", ""))
    summary = f"[calendardb] {service} {series} {value}".strip()
    return summary, MARKER + "\n" + json.dumps(
        record, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )


def decode(description):
    if not description or not description.startswith(MARKER + "\n"):
        return None
    record = json.loads(description[len(MARKER) + 1 :])
    if not isinstance(record, dict):
        raise ValueError("CalendarDB records must be JSON objects")
    return record
