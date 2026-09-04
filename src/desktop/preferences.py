from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Literal, cast

DesktopLanguage = Literal["mn", "en", "auto"]
SUPPORTED_DESKTOP_LANGUAGES = frozenset({"mn", "en", "auto"})


@dataclass(frozen=True)
class DesktopPreferences:
    """User-selected desktop dictation preferences shared by local processes."""

    selected_language: DesktopLanguage = "auto"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class DesktopPreferencesStore:
    """Persist desktop preferences with atomic JSON replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()

    def read(self) -> DesktopPreferences:
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                return DesktopPreferences()
            if not isinstance(payload, dict):
                return DesktopPreferences()
            value = payload.get("selected_language")
            if value not in SUPPORTED_DESKTOP_LANGUAGES:
                return DesktopPreferences()
            return DesktopPreferences(selected_language=value)

    def update(self, selected_language: str) -> DesktopPreferences:
        if selected_language not in SUPPORTED_DESKTOP_LANGUAGES:
            raise ValueError("selected_language must be 'mn', 'en', or 'auto'")
        with self._lock:
            preferences = DesktopPreferences(selected_language=cast(DesktopLanguage, selected_language))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary_path.write_text(
                json.dumps(preferences.as_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
            return preferences
