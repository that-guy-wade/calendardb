"""An offline backend for examples and tests."""

import copy

from .timestamps import in_range, parse_timestamp


class FakeBackend:
    def __init__(self):
        self._records = {}

    def create_record(self, record):
        record_id = record["_id"]
        if record_id in self._records and self._records[record_id] != record:
            raise ValueError("Record ID already exists with different data")
        self._records[record_id] = copy.deepcopy(record)
        return record_id

    def get_records(self, after=None, before=None, q=None):
        if q:
            raise NotImplementedError("Native Calendar search requires CalendarBackend")
        start, end = [
            None if value is None else parse_timestamp(value) for value in (after, before)
        ]
        return [
            copy.deepcopy(record)
            for record in self._records.values()
            if in_range(parse_timestamp(record["_ts"]), start, end)
        ]

    def get_record(self, record_id):
        return copy.deepcopy(self._records.get(record_id))

    def delete_record(self, record_id):
        self._records.pop(record_id, None)
