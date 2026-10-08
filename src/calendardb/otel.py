from datetime import datetime, timezone

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class CalendarSpanExporter(SpanExporter):
    """Export OpenTelemetry spans to Calendar. Your traces are now calendar events."""

    def __init__(self, client=None):
        if client is None:
            from .client import Client

            client = Client()
        self._client = client

    def export(self, spans):
        try:
            for span in spans:
                ctx = span.get_span_context()
                self._client.put(
                    {
                        "_id": f"span-{ctx.trace_id:032x}-{ctx.span_id:016x}",
                        "kind": "span",
                        "name": span.name,
                        "trace_id": format(ctx.trace_id, "032x"),
                        "span_id": format(ctx.span_id, "016x"),
                        "start": span.start_time,
                        "_ts": datetime.fromtimestamp(
                            span.start_time / 1_000_000_000, timezone.utc
                        ),
                        "end": span.end_time,
                    }
                )
            self._client.flush()
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self):
        self._client.flush()

    def force_flush(self, timeout_millis=30000):
        try:
            self._client.flush()
            return True
        except Exception:
            return False
