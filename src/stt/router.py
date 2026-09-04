from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Literal

from src.core.config import AppConfig

from .engine import STTEngine


STTLanguage = Literal["mn", "en", "auto"]


class STTLanguageRouter:
    """Route transcription to one language-specific engine at a time."""

    def __init__(
        self,
        config: AppConfig,
        *,
        mongolian: STTEngine | None = None,
        english: STTEngine | None = None,
        detector: STTEngine | None = None,
    ) -> None:
        self._engines: dict[str, STTEngine] = {
            "mn": mongolian or STTEngine(config, language="mn"),
            "en": english or STTEngine(config, language="en"),
        }
        self._detector = detector or STTEngine(config, language="auto")
        self._active_language: str | None = None
        self._detected_language: str | None = None
        self._lock = RLock()

    @property
    def loaded(self) -> bool:
        return self._active_language is not None and self._engines[self._active_language].loaded

    @property
    def active_language(self) -> str | None:
        return self._active_language

    @property
    def detected_language(self) -> str | None:
        """Return the language detected for the most recent transcription."""
        return self._detected_language

    @staticmethod
    def _select(language: STTLanguage) -> str:
        return "mn" if language == "auto" else language

    def _activate(self, language: str) -> STTEngine:
        if language not in self._engines:
            raise ValueError(f"Unsupported STT language: {language}")
        if self._active_language == language and self._engines[language].loaded:
            return self._engines[language]
        if self._active_language is not None:
            self._engines[self._active_language].unload()
        engine = self._engines[language]
        engine.load()
        self._active_language = language
        return engine

    def load(self) -> None:
        with self._lock:
            self._activate("mn")

    def unload(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.unload()
            self._detector.unload()
            self._active_language = None
            self._detected_language = None
    def transcribe(
        self,
        audio: str | Path,
        language: STTLanguage = "mn",
    ) -> str:
        with self._lock:
            if language == "auto":
                try:
                    detected = self._detector.detect_language(audio)
                finally:
                    self._detector.unload()
                if detected not in self._engines:
                    raise ValueError(f"Unsupported detected STT language: {detected}")
                self._detected_language = detected
                engine = self._activate(detected)
                return engine.transcribe(audio, language=detected)

            selected = self._select(language)
            engine = self._activate(selected)
            self._detected_language = selected
            return engine.transcribe(audio, language=selected)
