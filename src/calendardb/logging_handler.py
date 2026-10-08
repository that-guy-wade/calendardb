from datetime import datetime, timezone
import logging


class CalendarHandler(logging.Handler):
    """Route Python log records into Calendar. Do not use this."""

    def __init__(self, client=None, level=logging.NOTSET):
        super().__init__(level)
        if client is None:
            from .client import Client

            client = Client()
        self._client = client

    def emit(self, record):
        try:
            self._client.put(
                {
                    "level": record.levelname,
                    "msg": record.getMessage(),
                    "logger": record.name,
                    "line": record.lineno,
                    "ts_epoch": record.created,
                    "_ts": datetime.fromtimestamp(record.created, timezone.utc),
                }
            )
        except Exception:
            self.handleError(record)

    def flush(self):
        self._client.flush()

    def close(self):
        try:
            self._client.flush()
        finally:
            super().close()
