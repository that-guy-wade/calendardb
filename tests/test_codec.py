import pytest

from calendardb import codec


def test_lossless_event_description_round_trip():
    record = {"_id": "abc", "_ts": "2026-10-08T09:30:00Z", "value": {"city": "Montréal"}}
    title, body = codec.encode(record)
    assert title.startswith("[calendardb]")
    assert codec.decode(body) == record
    assert codec.decode("my appointment") is None


def test_invalid_marked_payload_fails():
    with pytest.raises(ValueError):
        codec.decode(codec.MARKER + "\n[]")
    with pytest.raises(ValueError):
        codec.decode(codec.MARKER + "\nnot json")
