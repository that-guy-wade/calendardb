"""A buffered time series client backed by Google Calendar events."""

from datetime import datetime, timezone
import json
import uuid

from .buffer import Buffer
from .timestamps import format_timestamp, in_range, parse_timestamp


class Client:
    def __init__(self, backend=None, flush_size=50, flush_interval=5.0, calendar="CalendarDB"):
        if backend is None:
            from .backend_calendar import CalendarBackend

            backend = CalendarBackend(calendar=calendar)
        self._backend = backend
        self._buffer = Buffer(self._flush_batch, flush_size, flush_interval)

    def put(self, record):
        rec = dict(record)
        rec.setdefault("_id", uuid.uuid4().hex)
        if not isinstance(rec["_id"], str) or not rec["_id"]:
            raise ValueError("Record IDs must be non-empty strings")
        rec["_ts"] = format_timestamp(rec.get("_ts", datetime.now(timezone.utc)))
        rec = json.loads(json.dumps(rec, ensure_ascii=False, allow_nan=False))
        self._buffer.add(rec)
        return rec["_id"]

    def _flush_batch(self, batch):
        for record in batch:
            self._backend.create_record(record)

    def flush(self):
        self._buffer.flush()

    def get(self, record_id):
        self.flush()
        return self._backend.get_record(record_id)

    def delete(self, record_id):
        self.flush()
        self._backend.delete_record(record_id)

    def query(self, after=None, before=None, contains=None, calendar_query=None, series=None):
        """Return records in [after, before), ordered by timestamp."""
        start, end = [
            None if value is None else parse_timestamp(value) for value in (after, before)
        ]
        if start is not None and end is not None and start >= end:
            raise ValueError("before must be later than after")
        self.flush()
        records = self._backend.get_records(after=start, before=end, q=calendar_query)
        records = filter(
            lambda record: in_range(parse_timestamp(record["_ts"]), start, end), records
        )
        records = filter(lambda record: series is None or record.get("series") == series, records)
        records = filter(
            lambda record: contains is None or contains in json.dumps(record, ensure_ascii=False),
            records,
        )
        return sorted(
            records,
            key=lambda record: parse_timestamp(record["_ts"]),
        )
