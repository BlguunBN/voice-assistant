from __future__ import annotations

from pathlib import Path

from src.desktop.overlay import DesktopOverlayHost
from src.desktop.status import DesktopStatusStore


def test_native_host_shows_active_states_and_hides_when_armed(tmp_path: Path) -> None:
    status_path = tmp_path / "desktop-status.json"
    store = DesktopStatusStore(status_path)
    host = DesktopOverlayHost(status_path)

    store.update("listening")
    host._sync_status()
    assert host._state == "listening"
    assert host._should_show() is True

    store.update("armed")
    host._sync_status()
    assert host._should_show() is False

    store.update("success", transcript="Сайн байна уу")
    host._sync_status()
    assert host._state == "success"
    assert host._should_show() is True
