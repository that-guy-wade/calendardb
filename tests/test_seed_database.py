import pytest

from examples.seed_database import DEMO_MARKER, records_for_demo, seed
from calendardb import Client, FakeBackend


def test_demo_corpus_is_deterministic_and_has_expected_series():
    first = records_for_demo("2026-10-08")
    second = records_for_demo("2026-10-08")
    assert first == second
    assert len(first) == 12
    assert all(row["_demo"] == DEMO_MARKER and row["service"] == "api" for row in first)
    assert [row["value"] for row in first if row["series"] == "latency_ms"] == [
        90,
        95,
        110,
        480,
        120,
        100,
    ]
    assert [row["value"] for row in first if row["series"] == "errors"] == [0, 0, 1, 12, 1, 0]
    assert len({row["_id"] for row in first}) == 12


def test_seed_verifies_range_peak_and_preserves_other_records():
    backend = FakeBackend()
    client = Client(backend=backend, flush_interval=None)
    protected = {"_id": "keep-me", "_ts": "2026-10-08T09:25:00Z", "note": "existing"}
    client.put(protected)
    client.flush()

    first = seed(client, "2026-10-08")
    second = seed(client, "2026-10-08")

    assert len(first["records"]) == 12
    assert len(second["records"]) == 12
    assert len(second["window"]) == 4
    assert second["latency_peak"]["value"] == 480
    assert second["latency_peak"]["_ts"] == "2026-10-08T09:30:00Z"
    assert protected in second["all_records"]
    assert len(second["all_records"]) == 13


def test_existing_demo_id_with_different_payload_is_rejected():
    backend = FakeBackend()
    client = Client(backend=backend, flush_interval=None)
    existing = records_for_demo("2026-10-08")[0] | {"value": -1}
    backend.create_record(existing)

    with pytest.raises(RuntimeError, match="conflicts with demo ID"):
        seed(client, "2026-10-08")


def test_verification_does_not_depend_on_tie_order_or_other_rows_in_range():
    class ReverseTiesBackend(FakeBackend):
        def get_records(self, after=None, before=None, q=None):
            return list(reversed(super().get_records(after=after, before=before, q=q)))

    backend = ReverseTiesBackend()
    client = Client(backend=backend, flush_interval=None)
    unrelated = {"_id": "other", "_ts": "2026-10-08T09:30:00Z", "series": "other"}
    client.put(unrelated)
    client.flush()

    result = seed(client, "2026-10-08")

    assert len(result["window"]) == 4
    assert unrelated in result["all_records"]


def test_default_corpus_uses_current_utc_day():
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date()
    assert {row["_ts"][:10] for row in records_for_demo()} == {today.isoformat()}
