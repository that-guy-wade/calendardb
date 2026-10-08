from datetime import datetime, timezone

import pytest

from calendardb import Client, FakeBackend


def client(backend=None):
    return Client(backend=backend or FakeBackend(), flush_interval=None)


def test_utc_normalization_and_half_open_time_window():
    db = client()
    ids = [
        db.put({"_ts": timestamp, "series": "latency", "value": value})
        for timestamp, value in [
            ("2026-10-08T11:59:59Z", 1),
            ("2026-10-08T05:00:00-07:00", 2),
            ("2026-10-08T12:00:00.500000Z", 3),
            ("2026-10-08T12:00:01Z", 4),
        ]
    ]
    rows = db.query(after="2026-10-08T12:00:00Z", before="2026-10-08T12:00:01Z")
    assert [record["value"] for record in rows] == [2, 3]
    assert db.get(ids[1])["_ts"] == "2026-10-08T12:00:00Z"
    assert len(db.query(before="2026-10-08T12:00:00.700000Z")) == 3


def test_snapshots_input_nested_data_and_handles_unicode():
    db = client()
    record = {"series": "cpu", "nested": {"city": "Montréal"}}
    record_id = db.put(record)
    record["nested"]["city"] = "changed"
    assert db.query(contains="Montréal")[0]["nested"]["city"] == "Montréal"
    assert db.query(series="other") == []
    db.delete(record_id)
    assert db.get(record_id) is None


@pytest.mark.parametrize("timestamp", ["2026-10-08", "2026-10-08T12:00:00", datetime(2026, 10, 8)])
def test_rejects_ambiguous_timestamps_before_writing(timestamp):
    db = client()
    with pytest.raises(ValueError):
        db.put({"_ts": timestamp})
    assert db.query() == []


def test_invalid_range_does_not_flush_pending_writes():
    backend = FakeBackend()
    db = client(backend)
    db.put({"value": 1})
    with pytest.raises(ValueError):
        db.query(after="2026-10-08T12:00:00Z", before="2026-10-08T12:00:00Z")
    assert backend.get_records() == []
    db.flush()


def test_partial_batch_retry_is_idempotent():
    class InterruptedBackend(FakeBackend):
        failed = False

        def create_record(self, record):
            if record["_id"] == "second" and not self.failed:
                self.failed = True
                raise OSError("connection lost")
            return super().create_record(record)

    backend = InterruptedBackend()
    db = client(backend)
    db.put({"_id": "first", "value": 1})
    db.put({"_id": "second", "value": 2})
    with pytest.raises(OSError):
        db.flush()
    db.flush()
    assert len(db.query()) == 2


def test_fake_backend_refuses_native_search_and_conflicting_ids():
    db = client()
    with pytest.raises(NotImplementedError):
        db.query(calendar_query="cpu")
    db.put({"_id": "id", "_ts": "2026-10-08T12:00:00Z", "value": 1})
    db.flush()
    with pytest.raises(ValueError):
        db._backend.create_record({"_id": "id", "_ts": "2026-10-08T12:00:00Z", "value": 2})


def test_aware_datetime_input_and_bad_json_validation():
    db = client()
    record_id = db.put({"_ts": datetime(2026, 10, 8, tzinfo=timezone.utc)})
    assert db.get(record_id)["_ts"] == "2026-10-08T00:00:00Z"
    with pytest.raises(ValueError):
        db.put({"value": float("nan")})
    with pytest.raises(ValueError):
        db.put({"_id": ""})
