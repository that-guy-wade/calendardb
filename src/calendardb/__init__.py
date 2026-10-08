from .backend import FakeBackend
from .client import Client
from .logging_handler import CalendarHandler

__all__ = ["Client", "FakeBackend", "CalendarHandler"]


def __getattr__(name):
    if name == "CalendarSpanExporter":
        from .otel import CalendarSpanExporter

        return CalendarSpanExporter
    raise AttributeError(name)
