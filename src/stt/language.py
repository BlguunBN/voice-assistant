"""Language types and normalization shared by speech-to-text engines."""

from __future__ import annotations

from typing import Literal

STTLanguage = Literal["mn", "en", "auto"]
DetectedLanguage = Literal["mn", "en"]

_LANGUAGE_ALIASES: dict[str, DetectedLanguage] = {
    "mn": "mn",
    "mongolian": "mn",
    "en": "en",
    "english": "en",
}


def normalize_detected_language(value: object) -> DetectedLanguage | None:
    """Return an API-supported language code, or ``None`` for unknown labels."""
    if not isinstance(value, str):
        return None
    return _LANGUAGE_ALIASES.get(value.strip().lower())
