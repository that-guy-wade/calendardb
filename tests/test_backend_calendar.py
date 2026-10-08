import json
import hashlib
import urllib.error
import urllib.parse
import unittest
from datetime import timedelta

from calendardb import backend_calendar as backend

API_PREFIX = urllib.parse.urlsplit(backend.BASE).path
CALENDAR_LIST_PATH = API_PREFIX + backend.CALENDAR_LIST
CALENDARS_PATH = API_PREFIX + backend.CALENDARS


class Response:
    def __init__(self, data=None):
        self.data = json.dumps(data or {}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.data


def event(record, event_id=None, marker=True, **updates):
    summary, description = backend.codec.encode(record)
    start = backend.timestamps.parse_timestamp(record["_ts"])
    payload = {
        "id": event_id or backend.CalendarBackend._event_id(record),
        "summary": summary,
        "description": description,
        "start": {"dateTime": backend.timestamps.format_timestamp(start)},
        "end": {"dateTime": backend.timestamps.format_timestamp(start + timedelta(seconds=1))},
        "extendedProperties": {"private": {backend.PROPERTY: "1"} if marker else {}},
    }
    payload.update(updates)
    return payload


class CalendarBackendTests(unittest.TestCase):
    def make_backend(self, handler, name="CalendarDB"):
        def http(request, timeout=None):
            self.assertEqual(timeout, 30)
            return Response(handler(request))

        return backend.CalendarBackend(token="test", http=http, calendar=name)

    @staticmethod
    def owned_calendar(calendar_id="cal/id?x", summary="CalendarDB", description=backend.MARKER):
        return {
            "id": calendar_id,
            "summary": summary,
            "description": description,
            "accessRole": "owner",
        }

    @staticmethod
    def calendar_list(request):
        return urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)

    def test_discovers_paginated_exact_owned_nonprimary_calendar(self):
        requests = []

        def handle(request):
            url = urllib.parse.urlsplit(request.full_url)
            requests.append(url)
            query = urllib.parse.parse_qs(url.query)
            if "pageToken" not in query:
                return {
                    "items": [
                        self.owned_calendar("primary", description=backend.MARKER)
                        | {"primary": True},
                        self.owned_calendar("shared") | {"accessRole": "writer"},
                    ],
                    "nextPageToken": "next /?",
                }
            self.assertEqual(query["pageToken"], ["next /?"])
            return {"items": [self.owned_calendar()]}

        result = self.make_backend(handle)._find_calendar()
        self.assertEqual(result, "cal/id?x")
        self.assertEqual(len(requests), 2)
        self.assertIn("pageToken=next+%2F%3F", requests[1].query)

    def test_rejects_multiple_calendar_matches_and_creates_when_missing(self):
        def duplicate(request):
            return {"items": [self.owned_calendar("one"), self.owned_calendar("two")]}

        with self.assertRaisesRegex(backend.CalendarBackendError, "Multiple"):
            self.make_backend(duplicate)._find_calendar()

        calls = []

        def create(request):
            calls.append((request.method, urllib.parse.urlsplit(request.full_url).path))
            if request.method == "GET":
                return {"items": [self.owned_calendar("primary") | {"primary": True}]}
            payload = json.loads(request.data)
            self.assertEqual(payload, {"summary": "CalendarDB", "description": backend.MARKER})
            return {"id": "created"}

        self.assertEqual(self.make_backend(create)._get_calendar(create=True), "created")
        self.assertEqual(calls, [("GET", CALENDAR_LIST_PATH), ("POST", CALENDARS_PATH)])

    def test_insert_uses_safe_private_event_and_deterministic_id(self):
        record = {"_id": "record 1", "_ts": "2026-01-01T00:00:00.123456Z", "message": "hi"}
        calls = []

        def handle(request):
            path = urllib.parse.urlsplit(request.full_url).path
            calls.append(request)
            if path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar()]}
            self.assertEqual(request.method, "POST")
            self.assertIn("/cal%2Fid%3Fx/events", request.full_url)
            self.assertIn("sendUpdates=none", request.full_url)
            payload = json.loads(request.data)
            self.assertEqual(payload["id"], hashlib.sha256(b"record 1").hexdigest())
            self.assertEqual(payload["start"]["dateTime"], "2026-01-01T00:00:00.123456Z")
            self.assertEqual(payload["end"]["dateTime"], "2026-01-01T00:00:01.123456Z")
            self.assertEqual(payload["visibility"], "private")
            self.assertEqual(payload["transparency"], "transparent")
            self.assertEqual(payload["reminders"], {"useDefault": False, "overrides": []})
            self.assertEqual(payload["extendedProperties"], {"private": {"calendarDB": "1"}})
            self.assertNotIn("attendees", payload)
            return {"id": payload["id"]}

        store = self.make_backend(handle)
        expected = hashlib.sha256(b"record 1").hexdigest()
        self.assertEqual(store.create_record(record), expected)
        self.assertEqual(len(calls), 2)

    def test_lists_scoped_and_paginated_events_with_exact_time_filters(self):
        first = {"_id": "one", "_ts": "2026-01-01T00:00:00Z", "message": "first"}
        second = {"_id": "two", "_ts": "2026-01-01T00:00:02Z", "message": "second"}
        requests = []

        def handle(request):
            url = urllib.parse.urlsplit(request.full_url)
            if url.path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar()]}
            query = urllib.parse.parse_qs(url.query)
            requests.append(query)
            self.assertEqual(query["privateExtendedProperty"], ["calendarDB=1"])
            self.assertEqual(query["showDeleted"], ["false"])
            self.assertEqual(query["singleEvents"], ["true"])
            self.assertEqual(query["orderBy"], ["startTime"])
            self.assertEqual(query["q"], ["error"])
            self.assertEqual(query["timeMin"], ["2026-01-01T00:00:00Z"])
            self.assertEqual(query["timeMax"], ["2026-01-01T00:00:03Z"])
            if "pageToken" not in query:
                return {
                    "items": [
                        event(first),
                        event({"_id": "outside", "_ts": "2025-12-31T23:59:59Z"}),
                        event(first, marker=False),
                        event(first, recurringEventId="parent"),
                        event(first, recurrence=["RRULE:FREQ=DAILY"]),
                        event(first, start={"dateTime": "2026-01-01T00:00:01Z"}),
                        event(first, end={"dateTime": "2026-01-01T00:00:02Z"}),
                        {
                            **event(first),
                            "description": backend.MARKER + '\n{"_id":"missing-ts"}',
                        },
                    ],
                    "nextPageToken": "page 2",
                }
            self.assertEqual(query["pageToken"], ["page 2"])
            return {"items": [event(second)]}

        records = self.make_backend(handle).get_records(
            after="2026-01-01T00:00:00Z", before="2026-01-01T00:00:02.500000Z", q="error"
        )
        self.assertEqual(records, [first, second])
        self.assertEqual(len(requests), 2)

    def test_get_record_and_delete_guard_unmarked_or_mismatched_records(self):
        record = {"_id": "abc", "_ts": "2026-01-01T00:00:00Z"}
        calls = []

        def handle(request):
            url = urllib.parse.urlsplit(request.full_url)
            if url.path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar("calendar")]}
            calls.append(request.method)
            if request.method == "GET":
                return event(record, marker=False)
            self.fail("unmarked event must not be deleted")

        store = self.make_backend(handle)
        self.assertIsNone(store.get_record("abc"))
        self.assertFalse(store.delete_record("abc"))
        self.assertEqual(calls, ["GET", "GET"])

    def test_delete_only_deletes_verified_record(self):
        record = {"_id": "abc", "_ts": "2026-01-01T00:00:00Z"}
        methods = []

        def handle(request):
            url = urllib.parse.urlsplit(request.full_url)
            if url.path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar("calendar")]}
            methods.append(request.method)
            if request.method == "GET":
                return event(record)
            return {}

        self.assertTrue(self.make_backend(handle).delete_record("abc"))
        self.assertEqual(methods, ["GET", "DELETE"])

    def test_conflict_is_idempotent_only_for_identical_record_and_timing(self):
        record = {"_id": "abc", "_ts": "2026-01-01T00:00:00Z", "v": 1}

        def handle(request):
            url = urllib.parse.urlsplit(request.full_url)
            if url.path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar("calendar")]}
            if request.method == "POST":
                raise urllib.error.HTTPError(request.full_url, 409, "private body", {}, None)
            return event(
                record,
                start={"dateTime": "2026-01-01T00:00:00+00:00"},
                end={"dateTime": "2026-01-01T00:00:01+00:00"},
            )

        self.assertEqual(
            self.make_backend(handle).create_record(record),
            backend.CalendarBackend._event_id(record),
        )

        def different(request):
            url = urllib.parse.urlsplit(request.full_url)
            if url.path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar("calendar")]}
            if request.method == "POST":
                raise urllib.error.HTTPError(request.full_url, 409, "private body", {}, None)
            return event({**record, "v": 2})

        with self.assertRaisesRegex(backend.CalendarBackendError, "conflict"):
            self.make_backend(different).create_record(record)

    def test_conflict_rejects_index_times_that_do_not_match_record_timestamp(self):
        record = {"_id": "abc", "_ts": "2026-01-01T00:00:00Z", "v": 1}

        def handle(request):
            url = urllib.parse.urlsplit(request.full_url)
            if url.path == CALENDAR_LIST_PATH:
                return {"items": [self.owned_calendar("calendar")]}
            if request.method == "POST":
                raise urllib.error.HTTPError(request.full_url, 409, "private body", {}, None)
            return event(record, start={"dateTime": "2026-01-01T00:00:05Z"})

        with self.assertRaisesRegex(backend.CalendarBackendError, "conflict"):
            self.make_backend(handle).create_record(record)

    def test_http_error_does_not_expose_response_body(self):
        def failed(request):
            raise urllib.error.HTTPError(request.full_url, 429, "secret body", {}, None)

        with self.assertRaisesRegex(backend.CalendarBackendError, "HTTP 429") as raised:
            self.make_backend(failed)._find_calendar()
        self.assertNotIn("secret body", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
