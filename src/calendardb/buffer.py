import atexit
import threading


class Buffer:
    """Batch records by size or time, retaining them if a write fails."""

    def __init__(self, flush_fn, flush_size=50, flush_interval=5.0):
        if flush_size < 1 or (flush_interval is not None and flush_interval < 0):
            raise ValueError("flush_size must be positive and flush_interval non-negative")
        self._flush_fn = flush_fn
        self._flush_size = flush_size
        self._flush_interval = flush_interval
        self._records = []
        self._lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._timer = None
        atexit.register(self.flush)

    def add(self, record):
        with self._lock:
            self._records.append(record)
            due = len(self._records) >= self._flush_size
            if self._flush_interval and self._timer is None:
                self._timer = threading.Timer(self._flush_interval, self.flush)
                self._timer.daemon = True
                self._timer.start()
        if due:
            self.flush()

    def flush(self):
        with self._flush_lock:
            with self._lock:
                batch, self._records = self._records, []
                if self._timer is not None:
                    self._timer.cancel()
                    self._timer = None
            if batch:
                try:
                    self._flush_fn(batch)
                except Exception:
                    with self._lock:
                        self._records = batch + self._records
                    raise
