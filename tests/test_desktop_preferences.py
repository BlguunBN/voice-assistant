from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.desktop.preferences import DesktopPreferencesStore


def test_preferences_default_to_auto_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "desktop-preferences.json"
    store = DesktopPreferencesStore(path)

    assert store.read().selected_language == "auto"
    updated = store.update("en")

    assert updated.selected_language == "en"
    assert store.read().selected_language == "en"
    assert json.loads(path.read_text(encoding="utf-8")) == {"selected_language": "en"}
    assert not path.with_suffix(".json.tmp").exists()


def test_preferences_reject_unsupported_language(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="selected_language"):
        DesktopPreferencesStore(tmp_path / "desktop-preferences.json").update("fr")


def test_preferences_recover_from_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "desktop-preferences.json"
    path.write_text("not json", encoding="utf-8")

    assert DesktopPreferencesStore(path).read().selected_language == "auto"
