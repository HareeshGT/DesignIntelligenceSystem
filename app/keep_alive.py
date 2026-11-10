"""Optional background keep-alive pinger, independent of FastAPI requests."""

import logging
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

log = logging.getLogger("dis.keep_alive")
INTERVAL_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10

_monitor_lock = threading.Lock()
_monitor_thread: threading.Thread | None = None
_monitor_stop_event: threading.Event | None = None


def start_keep_alive():
    """Start one optional pinger and return its shutdown event."""
    global _monitor_thread, _monitor_stop_event

    url = os.getenv("KEEP_ALIVE_URL", "").strip()
    if not url:
        log.info("Keep-alive monitor disabled: KEEP_ALIVE_URL is not configured")
        return None

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        log.warning("Keep-alive monitor disabled: KEEP_ALIVE_URL must be an HTTP(S) URL")
        return None

    with _monitor_lock:
        if _monitor_thread is not None and _monitor_thread.is_alive():
            return _monitor_stop_event

        stop_event = threading.Event()

        def ping_loop():
            while not stop_event.wait(INTERVAL_SECONDS):
                request = Request(url, headers={"User-Agent": "DesignIntelligenceSystem-KeepAlive/1.0"})
                try:
                    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                        log.info("Keep-alive ping completed: HTTP %s", response.status)
                except HTTPError as exc:
                    log.warning("Keep-alive target responded with HTTP %s", exc.code)
                except (URLError, TimeoutError, OSError) as exc:
                    log.warning("Keep-alive ping failed: %s", exc)

        thread = threading.Thread(target=ping_loop, name="dis-keep-alive", daemon=True)
        _monitor_stop_event = stop_event
        _monitor_thread = thread
        thread.start()
        log.info("Keep-alive monitor started (interval=%ss, timeout=%ss)", INTERVAL_SECONDS, REQUEST_TIMEOUT_SECONDS)
        return stop_event


def stop_keep_alive():
    """Stop the optional pinger during application shutdown."""
    global _monitor_thread, _monitor_stop_event

    with _monitor_lock:
        stop_event = _monitor_stop_event
        thread = _monitor_thread
        if stop_event is None:
            return
        stop_event.set()

    # urlopen is bounded by REQUEST_TIMEOUT_SECONDS; do not leave the worker
    # behind when the application shuts down.
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=REQUEST_TIMEOUT_SECONDS + 1)

    with _monitor_lock:
        if _monitor_thread is thread and (thread is None or not thread.is_alive()):
            _monitor_thread = None
            _monitor_stop_event = None
