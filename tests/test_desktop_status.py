from __future__ import annotations

import json
from pathlib import Path

from src.desktop.status import DesktopStatusStore


def test_status_store_round_trips_transcript_and_error(tmp_path: Path) -> None:
    store = DesktopStatusStore(tmp_path / "desktop-status.json")

    armed = store.clear()
    assert armed.status == "armed"
    assert armed.transcript is None

    listening = store.update("listening", transcript="")
    assert listening.status == "listening"
    assert listening.transcript == ""

    pasted = store.update(
        "pasting",
        transcript="Сайн байна уу",
        selected_language="auto",
        detected_language="mn",
    )
    assert pasted.status == "pasting"
    assert store.read().transcript == "Сайн байна уу"
    assert store.read().selected_language == "auto"
    assert store.read().detected_language == "mn"

    error = store.update("error", detail="STT failed")
    assert error.detail == "STT failed"
    assert store.read().transcript == "Сайн байна уу"
    assert store.read().detected_language == "mn"


def test_status_store_recovers_from_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "desktop-status.json"
    path.write_text("not json", encoding="utf-8")

    status = DesktopStatusStore(path).read()

    assert status.status == "offline"
    assert status.transcript is None
    assert status.updated_at == 0.0


def test_status_store_writes_utf8_json_atomically(tmp_path: Path) -> None:
    path = tmp_path / "desktop-status.json"
    DesktopStatusStore(path).update("pasting", transcript="Монгол хэл")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["status"] == "pasting"
    assert payload["transcript"] == "Монгол хэл"
    assert not path.with_suffix(".json.tmp").exists()
