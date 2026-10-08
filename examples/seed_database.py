"""Seed and verify twelve synthetic CalendarDB API measurements."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import hashlib

from calendardb import Client, FakeBackend

DEMO_MARKER = "calendardb-demo-v1"
CALENDAR = "CalendarDB Demo"
TIMES = tuple(time(9, minute, tzinfo=timezone.utc) for minute in range(0, 60, 10))
SERIES = {"latency_ms": (90, 95, 110, 480, 120, 100), "errors": (0, 0, 1, 12, 1, 0)}


def records_for_demo(day: date | str | None = None) -> list[dict]:
    if day is None:
        day = datetime.now(timezone.utc).date()
    if isinstance(day, str):
        day = date.fromisoformat(day)
    records = []
    for series, values in SERIES.items():
        for at, value in zip(TIMES, values, strict=True):
            timestamp = datetime.combine(day, at)
            stamp = timestamp.isoformat().replace("+00:00", "Z")
            record_id = hashlib.sha256(f"{day.isoformat()}:{series}:{stamp}".encode()).hexdigest()
            records.append(
                {
                    "_id": record_id,
                    "_ts": stamp,
                    "_demo": DEMO_MARKER,
                    "service": "api",
                    "series": series,
                    "value": value,
                }
            )
    return sorted(records, key=lambda record: (record["_ts"], record["series"]))


def seed(client: Client, day: date | str | None = None) -> dict:
    expected = records_for_demo(day)
    previous = {record["_id"]: record for record in client.query()}
    for record in expected:
        existing = previous.get(record["_id"])
        if existing is not None and existing != record:
            raise RuntimeError(f"Existing record conflicts with demo ID {record['_id']}.")
        if existing is None:
            client.put(record)
    client.flush()
    actual = client.query()
    return verify(client, expected, actual, previous)


def _record_order(record: dict) -> tuple:
    return record["_ts"], record["series"]


def _verify_demo_rows(expected: list[dict], actual: list[dict]) -> list[dict]:
    day_key = expected[0]["_ts"][:10]
    demo_today = sorted(
        (
            row
            for row in actual
            if row.get("_demo") == DEMO_MARKER and row["_ts"].startswith(day_key)
        ),
        key=_record_order,
    )
    if demo_today != expected:
        raise RuntimeError("Seed readback mismatch: expected exactly twelve matching demo records.")
    return demo_today


def _verify_window(client: Client, expected: list[dict], day_key: str) -> list[dict]:
    start = f"{day_key}T09:20:00Z"
    end = f"{day_key}T09:40:00Z"
    window = client.query(after=start, before=end)
    demo_window = sorted(
        (row for row in window if row.get("_demo") == DEMO_MARKER), key=_record_order
    )
    expected_window = [row for row in expected if start <= row["_ts"] < end]
    if demo_window != expected_window:
        raise RuntimeError(
            "Seed readback mismatch: expected four records in the 09:20–09:40 range."
        )
    return demo_window


def _verify_peak(demo_today: list[dict], day_key: str) -> dict:
    latency_peak = max(
        (row for row in demo_today if row["series"] == "latency_ms"), key=lambda row: row["value"]
    )
    paired_errors = next(
        row for row in demo_today if row["series"] == "errors" and row["_ts"] == latency_peak["_ts"]
    )
    if (
        latency_peak["value"] != 480
        or latency_peak["_ts"] != f"{day_key}T09:30:00Z"
        or paired_errors["value"] != 12
    ):
        raise RuntimeError(
            "Seed readback mismatch: expected the 480 ms peak and 12 errors at 09:30."
        )
    return latency_peak


def verify(client: Client, expected: list[dict], actual: list[dict], previous: dict) -> dict:
    day_key = expected[0]["_ts"][:10]
    demo_today = _verify_demo_rows(expected, actual)
    current = {row["_id"]: row for row in actual}
    if any(current.get(record_id) != record for record_id, record in previous.items()):
        raise RuntimeError("Seed readback mismatch: pre-existing records were not preserved.")
    window = _verify_window(client, expected, day_key)
    latency_peak = _verify_peak(demo_today, day_key)
    return {
        "records": expected,
        "all_records": actual,
        "window": window,
        "latency_peak": latency_peak,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="seed and verify with an offline FakeBackend"
    )
    args = parser.parse_args(argv)
    backend = FakeBackend() if args.dry_run else None
    client = Client(backend=backend, calendar=CALENDAR)
    result = seed(client)
    mode = "offline FakeBackend" if args.dry_run else CALENDAR
    print(
        f"verified 12 synthetic records in {mode}; "
        f"range=4 peak={result['latency_peak']['value']}ms at {result['latency_peak']['_ts']} "
        f"errors=12"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
