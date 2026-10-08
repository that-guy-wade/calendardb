import pytest

pytest.importorskip("opentelemetry.sdk.trace")

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from calendardb import CalendarSpanExporter, Client
from calendardb.backend import FakeBackend


def test_exporter_writes_spans_to_backend():
    db = Client(backend=FakeBackend(), flush_size=100, flush_interval=None)
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(CalendarSpanExporter(client=db)))
    tracer = provider.get_tracer("test")

    with tracer.start_as_current_span("agent-step"):
        pass

    db.flush()
    rows = db.query()
    assert any(r.get("name") == "agent-step" and r.get("kind") == "span" for r in rows)


def test_export_reports_failure_if_calendar_write_fails():
    from opentelemetry.sdk.trace.export import SpanExportResult

    class FailedClient:
        def flush(self):
            raise RuntimeError("calendar unavailable")

    assert CalendarSpanExporter(client=FailedClient()).export([]) == SpanExportResult.FAILURE


def test_force_flush_returns_false_when_calendar_is_unavailable():
    class FailedClient:
        def flush(self):
            raise RuntimeError("calendar unavailable")

    assert CalendarSpanExporter(client=FailedClient()).force_flush() is False


def test_reexport_after_lost_write_response_does_not_duplicate_span():
    from types import SimpleNamespace

    from opentelemetry.sdk.trace.export import SpanExportResult

    class LostResponseBackend(FakeBackend):
        failed = False

        def create_record(self, record):
            record_id = super().create_record(record)
            if not self.failed:
                self.failed = True
                raise OSError("response lost after insertion")
            return record_id

    db = Client(backend=LostResponseBackend(), flush_interval=None)
    exporter = CalendarSpanExporter(client=db)
    span = SimpleNamespace(
        name="query",
        start_time=1_791_446_400_000_000_000,
        end_time=1_791_446_401_000_000_000,
        get_span_context=lambda: SimpleNamespace(trace_id=123, span_id=456),
    )
    assert exporter.export([span]) == SpanExportResult.FAILURE
    assert exporter.export([span]) == SpanExportResult.SUCCESS
    assert len(db.query()) == 1
