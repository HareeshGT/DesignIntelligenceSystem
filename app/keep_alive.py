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


def start_keep_alive():
    """Start the optional pinger when KEEP_ALIVE_URL is a valid HTTP(S) URL."""
    url = os.getenv("KEEP_ALIVE_URL", "").strip()
    if not url:
        log.info("Keep-alive monitor disabled: KEEP_ALIVE_URL is not configured")
        return None

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        log.warning("Keep-alive monitor disabled: KEEP_ALIVE_URL must be an HTTP(S) URL")
        return None

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
    thread.start()
    log.info("Keep-alive monitor started (interval=%ss, timeout=%ss)", INTERVAL_SECONDS, REQUEST_TIMEOUT_SECONDS)
    return stop_event
