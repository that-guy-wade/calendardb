# CalendarDB

CalendarDB is a tiny time-series store with a day view. It writes each record as a private, transparent one-second event in a dedicated Google Calendar, then reads the event description back as JSON. Your latency graph is now something you can scroll past on the way to lunch.

## Install

```sh
pip install 'calendardb[otel]'
```

## Run the synthetic demo from a source checkout

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[otel]'
python examples/seed_database.py --dry-run
```

The dry run uses the same `Client` and seed path as live mode, backed by an in-memory fake. It writes 12 synthetic API measurements for the current UTC day and verifies the complete readback. No Google account or network access is used.

For live storage, create an OAuth desktop client in Google Cloud, enable the Google Calendar API, download the desktop OAuth JSON outside this repository, and authorize CalendarDB:

```sh
calendardb login --client-secrets /path/outside/repository/client_secret.json
python examples/seed_database.py
```

The OAuth flow requests `calendar.app.created` and `calendar.calendarlist.readonly`. CalendarDB creates a separate `CalendarDB Demo` calendar and does not use your primary calendar. Keep the OAuth JSON out of source control; the refresh token is saved in your operating system keychain. `calendardb logout` removes that saved authorization.

## Use it

```python
from datetime import datetime, timedelta, timezone

from calendardb import Client

db = Client(calendar="CalendarDB Demo")
now = datetime.now(timezone.utc)
db.put({"service": "api", "series": "latency_ms", "value": 95, "_ts": now})
rows = db.query(after=now, before=now + timedelta(seconds=1), series="latency_ms")
print(rows[0]["value"])
```

`put` adds an aware UTC `_ts` timestamp and UUID `_id` when they are missing. `query` returns records in timestamp order; `after` includes its timestamp and `before` excludes its timestamp. `contains` searches serialized record text with a case-sensitive local match. `calendar_query` passes a text search to Google Calendar, and `series` matches the `series` field exactly. Buffered writes flush at 50 records or after five seconds by default, with one Calendar event per record. IDs are immutable: retrying the same ID and payload is safe; writing different data under an existing ID fails. `get(id)` reads a record and `delete(id)` removes only a verified CalendarDB event.

For standard Python logging, use `CalendarHandler` from `calendardb.logging_handler`. For OpenTelemetry, install the `otel` extra and configure `CalendarSpanExporter` from `calendardb.otel` as a span exporter. These are ordinary records under the same timestamp and event model; the Calendar UI does not become an observability dashboard by wishing very hard.

## What the calendar means

The event start time is the record timestamp. Each event description contains the record, and each summary is a short readable preview. The `series` field is just a record dimension. Calendar labels are not used, and CalendarDB does not create a database index: the event start time is the timestamp index, the event rows are the records, and the dedicated calendar is the collection.

Google's published account storage allowance lists Gmail, Drive, and Photos; Calendar is not listed there. The careful reading is that event text is outside that listed allowance, not that CalendarDB has unlimited storage. Attachments stored in Drive still count toward Drive storage. Calendar API quotas, general usage limits, and operational limits still apply. Google's current published API quotas for projects created on or after May 1, 2026 are 10,000 requests per minute per project and 600 per minute per user per project; the page describes a 1,000,000-request daily threshold before charges and says further billing details are planned for later in 2026. Google also applies undisclosed single-calendar write limits. Its [paid Workspace guidance](https://knowledge.workspace.google.com/admin/calendar/avoid-calendar-use-limits) warns about creating over 100,000 events or more than 60 calendars in a short period; stricter account limits are not fully public. These are activity limits, not a published total storage capacity.

CalendarDB is a satire/demo project. Google Calendar is a calendar, and event-based storage inherits calendar-shaped limits and ergonomics. A day view is not a query planner.

## Project

Adapted from [GranolaDB](https://github.com/that-guy-wade/granoladb), with Google Calendar events as the storage backend.

See [the demo walkthrough](docs/demo.md) and [launch copy](launch-thread.md). The demo values are synthetic and marked `calendardb-demo-v1`; they are not captured from a real service.

References: [Calendar API quotas and usage limits](https://developers.google.com/workspace/calendar/api/guides/quota), [Google storage policy](https://support.google.com/googleone/answer/6374270), [Gemini Apps and Google Calendar](https://support.google.com/gemini/answer/15305236).
