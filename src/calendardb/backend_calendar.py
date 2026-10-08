"""Google Calendar REST storage for CalendarDB records."""

from datetime import timedelta
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request

from . import codec, timestamps

BASE = "https://www.googleapis.com/calendar/v3"
CALENDAR_LIST = "/users/me/calendarList"
CALENDARS = "/calendars"
VERSION = "1"
MARKER = "CALENDARDB v1"
PROPERTY = "calendarDB"


class CalendarBackendError(RuntimeError):
    """Safe, user-facing Calendar API failure."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class CalendarBackend:
    def __init__(self, token=None, http=urllib.request.urlopen, calendar="CalendarDB"):
        self._token = token
        self._http = http
        self._calendar = calendar
        self._calendar_id = None

    def _request(self, method, path, payload=None):
        from .auth import get_access_token

        url = BASE + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        token = self._token if self._token is not None else get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._http(request, timeout=30) as response:
                content = response.read()
            return json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            raise CalendarBackendError(
                f"Calendar API request failed with HTTP {exc.code}", exc.code
            ) from None
        except (OSError, json.JSONDecodeError):
            raise CalendarBackendError("Calendar API request failed") from None

    @staticmethod
    def _calendar_path(calendar_id, suffix=""):
        return CALENDARS + "/" + urllib.parse.quote(calendar_id, safe="") + suffix

    def _find_calendar(self):
        token = None
        matches = []
        expected = {"summary": self._calendar, "description": MARKER, "accessRole": "owner"}
        while True:
            params = {"maxResults": 250}
            if token:
                params["pageToken"] = token
            result = self._request("GET", CALENDAR_LIST + "?" + urllib.parse.urlencode(params))
            for item in result.get("items", []):
                if not item.get("primary") and all(
                    item.get(key) == value for key, value in expected.items()
                ):
                    matches.append(item["id"])
            token = result.get("nextPageToken")
            if not token:
                break
        if len(matches) > 1:
            raise CalendarBackendError("Multiple CalendarDB calendars match this name")
        return matches[0] if matches else None

    def _get_calendar(self, create=False):
        calendar_id = self._calendar_id or self._find_calendar()
        if calendar_id or not create:
            self._calendar_id = calendar_id
            return calendar_id
        result = self._request(
            "POST", CALENDARS, {"summary": self._calendar, "description": MARKER}
        )
        calendar_id = result.get("id")
        if not calendar_id:
            raise CalendarBackendError("Calendar creation returned no calendar ID")
        self._calendar_id = calendar_id
        return calendar_id

    @staticmethod
    def _event_id(record):
        record_id = record.get("_id")
        if not isinstance(record_id, str) or not record_id:
            raise CalendarBackendError("CalendarDB record has no valid _id")
        return hashlib.sha256(record_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _decode_event(event):
        props = event.get("extendedProperties", {}).get("private", {})
        if any(
            (
                props.get(PROPERTY) != VERSION,
                event.get("status") == "cancelled",
                event.get("recurrence"),
                event.get("recurringEventId"),
                not event.get("id"),
            )
        ):
            return None
        try:
            record = codec.decode(event.get("description", ""))
        except (ValueError, TypeError):
            return None
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("_id"), str)
            or not record["_id"]
        ):
            return None
        try:
            record_time = timestamps.parse_timestamp(record["_ts"])
            start = timestamps.parse_timestamp(event["start"]["dateTime"])
            end = timestamps.parse_timestamp(event["end"]["dateTime"])
        except (KeyError, TypeError, ValueError):
            return None
        if start != record_time or end != record_time + timedelta(seconds=1):
            return None
        if CalendarBackend._event_id(record) != event["id"]:
            return None
        return record

    @staticmethod
    def _event_payload(record):
        summary, description = codec.encode(record)
        try:
            start = timestamps.parse_timestamp(record["_ts"])
        except (TypeError, ValueError, KeyError):
            raise CalendarBackendError("CalendarDB record has no valid timestamp") from None
        end = start + timedelta(seconds=1)
        return {
            "id": CalendarBackend._event_id(record),
            "summary": summary,
            "description": description,
            "start": {"dateTime": timestamps.format_timestamp(start)},
            "end": {"dateTime": timestamps.format_timestamp(end)},
            "visibility": "private",
            "transparency": "transparent",
            "reminders": {"useDefault": False, "overrides": []},
            "extendedProperties": {"private": {PROPERTY: VERSION}},
        }

    def create_record(self, record):
        payload = self._event_payload(record)
        calendar_id = self._get_calendar(create=True)
        path = self._calendar_path(calendar_id, "/events?sendUpdates=none")
        try:
            result = self._request("POST", path, payload)
        except CalendarBackendError as exc:
            if exc.status != 409:
                raise
            existing = self._request(
                "GET", self._calendar_path(calendar_id, "/events/" + payload["id"])
            )
            decoded = self._decode_event(existing)
            if decoded != record:
                raise CalendarBackendError("CalendarDB event ID conflict") from None
            return payload["id"]
        if result.get("id") != payload["id"]:
            raise CalendarBackendError("Calendar event insert returned an unexpected ID")
        return payload["id"]

    @staticmethod
    def _time_bounds(after, before):
        lower = timestamps.parse_timestamp(after) if after is not None else None
        upper = timestamps.parse_timestamp(before) if before is not None else None
        params = {}
        if lower is not None:
            params["timeMin"] = timestamps.format_timestamp(lower.replace(microsecond=0))
        if upper is not None:
            query_upper = upper.replace(microsecond=0) + timedelta(seconds=bool(upper.microsecond))
            params["timeMax"] = timestamps.format_timestamp(query_upper)
        return lower, upper, params

    def get_records(self, after=None, before=None, q=None):
        calendar_id = self._get_calendar()
        if not calendar_id:
            return []
        params = {
            "privateExtendedProperty": f"{PROPERTY}={VERSION}",
            "showDeleted": "false",
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 2500,
        }
        lower, upper, time_params = self._time_bounds(after, before)
        params.update(time_params)
        if q:
            params["q"] = q
        records = []
        page = None
        while True:
            query = dict(params)
            if page:
                query["pageToken"] = page
            result = self._request(
                "GET",
                self._calendar_path(calendar_id, "/events") + "?" + urllib.parse.urlencode(query),
            )
            for event in result.get("items", []):
                record = self._decode_event(event)
                if record is None:
                    continue
                if not timestamps.in_range(timestamps.parse_timestamp(record["_ts"]), lower, upper):
                    continue
                records.append(record)
            page = result.get("nextPageToken")
            if not page:
                return records

    def get_record(self, record_id):
        calendar_id = self._get_calendar()
        if not calendar_id:
            return None
        event_id = self._event_id({"_id": record_id})
        try:
            event = self._request("GET", self._calendar_path(calendar_id, "/events/" + event_id))
        except CalendarBackendError as exc:
            if exc.status == 404:
                return None
            raise
        record = self._decode_event(event)
        return record if record is not None and str(record.get("_id")) == str(record_id) else None

    def delete_record(self, record_id):
        calendar_id = self._get_calendar()
        if not calendar_id:
            return False
        event_id = self._event_id({"_id": record_id})
        try:
            event = self._request("GET", self._calendar_path(calendar_id, "/events/" + event_id))
        except CalendarBackendError as exc:
            if exc.status == 404:
                return False
            raise
        record = self._decode_event(event)
        if record is None or str(record.get("_id")) != str(record_id):
            return False
        self._request("DELETE", self._calendar_path(calendar_id, "/events/" + event_id))
        return True
