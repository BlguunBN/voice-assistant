from __future__ import annotations

from pathlib import Path

from src.desktop.overlay import DesktopOverlayHost
from src.desktop.status import DesktopStatusStore


def test_native_host_expands_for_activity_and_collapses_after_paste(tmp_path: Path) -> None:
    status_path = tmp_path / "desktop-status.json"
    store = DesktopStatusStore(status_path)
    host = DesktopOverlayHost(status_path)

    store.update("listening")
    host._sync_status()
    assert host._state == "listening"
    assert host._expanded is True

    store.update("armed")
    host._sync_status()
    assert host._expanded is False

    store.update("pasting", transcript="Сайн байна уу")
    host._sync_status()
    assert host._transcript == "Сайн байна уу"
    assert host._expanded is True
