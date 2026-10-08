1/5 CalendarDB: a time-series database with a day view. It stores each record as a private, transparent one-second Google Calendar event. Your query planner is a calendar.

2/5 The timestamp is the event start; the record is in the description. The calendar is the collection, event rows are records, and `series` is a field. No labels or database index required. (Because, technically, a calendar already has time.)

3/5 The synthetic demo seeds 12 API measurements. At 09:30, latency reaches 480 ms and errors hit 12. Query `[09:20, 09:40)` returns four rows. Then open Schedule view to admire the timestamp index.

4/5 Try it offline: `pip install -e '.[otel]'` then `python examples/seed_database.py --dry-run`. Live mode uses a dedicated app-created calendar after Google OAuth. The seed is deterministic and safe to rerun.

5/5 CalendarDB is satire, not unlimited storage or quota-free analytics. Calendar API limits still apply. Gemini can find Calendar events; grouping this demo by series or calculating its peak is unverified.
