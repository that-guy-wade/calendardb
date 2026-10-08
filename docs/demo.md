# CalendarDB demo: the incident has a day view

This demo writes twelve clearly marked, synthetic API measurements to a dedicated Google Calendar. Six `latency_ms` events and six `errors` events share the same timestamps at ten-minute intervals from 09:00 through 09:50 UTC. The latency values are `90, 95, 110, 480, 120, 100`; the error values are `0, 0, 1, 12, 1, 0`. Every record carries `_demo: calendardb-demo-v1`, `service: api`, a `series` name, and a deterministic `_id` derived from the UTC date, series, and time.

Run the local version first:

```sh
pip install -e '.[otel]'
python examples/seed_database.py --dry-run
```

Dry-run follows the same seed and query path as live mode, using an in-memory `FakeBackend`. It checks that the backend contains exactly the 12 expected rows for today's demo, that every record matches the expected payload, and that unrelated pre-existing records survive. Re-running the seed uses the same IDs and accepts an existing event only when its complete payload matches. A conflicting payload stops the seed rather than overwriting existing calendar data.

For a live Calendar run, create a Google Cloud project and enable **Google Calendar API** from **APIs & Services → Library**. Open **Google Auth Platform → Audience**, choose **External** for a personal test account, and keep the app in **Testing**. Add the Google account you will use under **Test users**. In **Data Access**, add these scopes:

- `https://www.googleapis.com/auth/calendar.app.created`
- `https://www.googleapis.com/auth/calendar.calendarlist.readonly`

Save the consent-screen changes. Open **Clients → Create client**, choose **Desktop app**, create the OAuth client, and download its JSON to a location outside the repository. This test project is limited to its listed test users; Google's current help says Testing projects allow up to 100 listed users and test-user authorizations expire after seven days. Then:

```sh
calendardb login --client-secrets /path/to/client_secret.json
python examples/seed_database.py
```

The consent flow requests `https://www.googleapis.com/auth/calendar.app.created` and `https://www.googleapis.com/auth/calendar.calendarlist.readonly`. These let CalendarDB create and manage the app-created demo calendar and find it again. The tool writes only to `CalendarDB Demo`, a secondary calendar. The refresh token goes into the OS keychain; `CALENDARDB_TOKEN` can supply a short-lived token for controlled automation. To remove keychain authorization, run `calendardb logout`.

Google's [OAuth setup guide](https://support.google.com/cloud/answer/13461325) documents External testing, adding test users, and creating credentials. Google's [OAuth audience guide](https://support.google.com/cloud/answer/15549945) documents the Testing user limit and seven-day test-user authorization lifetime. Console navigation labels can change; use the linked instructions if the labels differ.

## Record a 60-second demo

Use a Google account already added as a test user. Record the terminal and Calendar browser window; do not show OAuth client JSON or keychain contents. The demo writes only synthetic records to `CalendarDB Demo`.

| Time | Screen and action | Narration |
| --- | --- | --- |
| 0–6s | Terminal: run `python examples/seed_database.py --dry-run`. Keep the verification line visible. | “CalendarDB stores time-series records as calendar events. This dry run uses synthetic data and verifies the query.” |
| 6–14s | Show the current code/example with `_demo`, `service`, `series`, `_ts`, and `value` fields. | “Each event carries a timestamp, a series name, and a value. These measurements are invented for the demo.” |
| 14–24s | Switch to Google Calendar Schedule view. Select `CalendarDB Demo`, navigate to the current UTC date, and show all twelve entries from 09:00 through 09:50 UTC. | “There are twelve one-second events: six latency samples and six error counts. The event start is the timestamp index.” |
| 24–34s | Point to the 09:30 events. Open one latency event to show its JSON description, then show the 09:30 error event. | “At 09:30 the synthetic latency is 480 milliseconds, alongside 12 errors. This is a crafted example, not a real incident.” |
| 34–44s | Terminal: run the live readback snippet or show the script output for the `[09:20, 09:40)` range. Keep its four matching synthetic records visible. | “The range query includes 09:20 and excludes 09:40. It returns four measurements.” |
| 44–52s | Return to Schedule view. Zoom out enough to show the complete timeline. | “The collection is a dedicated calendar. Rows are events. Calendar labels and database indexes are not involved.” |
| 52–60s | Show the dry-run success and this README's quota note. | “CalendarDB is satire: the day view is real, while Calendar quotas and usage limits still apply.” |

Optional Gemini shot: only record it after confirming the app is connected and an authorized test account can read `CalendarDB Demo`. Ask `@Google Calendar` to show events around 09:30. Do not narrate series grouping, peak calculation, or cross-event analytics as demonstrated; those behaviors are unverified. If authorization is missing, leave this shot out and keep the demo pending rather than depicting a successful result.

## Verify the timeline

Open Google Calendar's **Schedule** view, select `CalendarDB Demo`, and inspect the twelve one-second events from 09:00 to 09:50 UTC. The event rows are the records; their start times are the timestamp index. There are no labels or separate database indexes. The calendar itself is the collection, and `series` is a field in each record.

The script verifies the range `09:20 <= _ts < 09:40` returns four records: latency 110 and 480, and errors 1 and 12. The highest latency is 480 ms at 09:30; the matching 09:30 error count is 12. CalendarDB is not claiming that a real incident happened. These are fabricated measurements designed to make the query visible in Calendar.

Optional: if Google Calendar is connected in Gemini Apps, try asking `@Google Calendar` to show the events in the `CalendarDB Demo` calendar around 09:30 UTC. Google's Gemini help documents finding events and requesting counts for date ranges. It does not establish that this setup will reliably group these records by `series`, compare values across events, or calculate the peak; those analytics remain unverified. Check the returned Calendar events before relying on a response.

## Operational notes

CalendarDB buffers writes and creates one Calendar event for each record when it flushes. The default is 50 records or five seconds. Small batches are useful for a demo, while every event still consumes a Calendar API request. Google's quota page currently lists, for projects created on or after May 1, 2026, 10,000 API requests per minute per project and 600 per minute per user per project. It also lists a 1,000,000-request daily threshold before charges and says fuller billing details are planned for later in 2026. Existing projects may retain older quotas, and general Calendar usage and operational limits also apply. Do not read this as a no-quota or unlimited-storage promise.

Google's listed shared storage allowance covers Gmail, Drive, and Photos, not Calendar. Event text is outside that listed Gmail/Drive/Photos storage allowance. This is a narrow statement about the published list, not a claim that Calendar accepts unlimited data. If an event references an attachment stored in Drive, that attachment counts toward Drive storage.

The project includes a standard-library logging handler and an optional OpenTelemetry span exporter (`pip install -e '.[otel]'`). Both use the same record writer, so event volume and Calendar API limits apply to telemetry too.

References: [Calendar API quotas and usage limits](https://developers.google.com/workspace/calendar/api/guides/quota), [Google storage policy](https://support.google.com/googleone/answer/6374270), [Gemini Apps: create and manage Calendar events](https://support.google.com/gemini/answer/15305236).
