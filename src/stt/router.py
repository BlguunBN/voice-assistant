from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Literal

from src.core.config import AppConfig
from .engine import STTEngine

STTLanguage = Literal["mn", "en", "auto"]


class STTLanguageRouter:
    """Compatibility facade around exactly one multilingual STT engine."""

    def __init__(self, config: AppConfig, *, engine: STTEngine | None = None) -> None:
        self._engine = engine or STTEngine(config, language="auto")
        self._lock = RLock()

    @property
    def loaded(self) -> bool:
        return self._engine.loaded

    @property
    def active_language(self) -> str | None:
        return self._engine.last_detected_language

    @property
    def detected_language(self) -> str | None:
        return self._engine.last_detected_language

    def load(self) -> None:
        with self._lock:
            self._engine.load()

    def unload(self) -> None:
        with self._lock:
            self._engine.unload()

    def transcribe(self, audio: str | Path, language: STTLanguage = "mn") -> str:
        with self._lock:
            return self._engine.transcribe(audio, language=language)
