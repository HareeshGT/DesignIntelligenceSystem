from app import keep_alive


def test_keep_alive_start_is_idempotent_and_shutdown_stops_worker(monkeypatch):
    monkeypatch.setenv("KEEP_ALIVE_URL", "https://example.com/health")
    monkeypatch.setattr(keep_alive, "INTERVAL_SECONDS", 60)

    first = keep_alive.start_keep_alive()
    second = keep_alive.start_keep_alive()

    assert first is not None
    assert second is first
    worker = keep_alive._monitor_thread
    assert worker is not None and worker.is_alive()

    keep_alive.stop_keep_alive()

    assert first.is_set()
    assert worker is not None and not worker.is_alive()
    assert keep_alive._monitor_thread is None
    assert keep_alive._monitor_stop_event is None


def test_keep_alive_stays_disabled_without_url(monkeypatch):
    monkeypatch.delenv("KEEP_ALIVE_URL", raising=False)
    keep_alive.stop_keep_alive()
    assert keep_alive.start_keep_alive() is None
