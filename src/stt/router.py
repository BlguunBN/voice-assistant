from __future__ import annotations

from pathlib import Path
from threading import RLock

from src.core.config import AppConfig
from .language import STTLanguage, normalize_detected_language
from .moonshine import MoonshineSTTEngine
from .qwen import QwenSTTEngine


class STTLanguageRouter:
    """Route Mongolian to Moonshine and English to Qwen, one model at a time."""

    def __init__(self, config: AppConfig, *, mongolian_engine: object | None = None, english_engine: object | None = None) -> None:
        self._mongolian = mongolian_engine or MoonshineSTTEngine(config)
        self._english = english_engine or QwenSTTEngine(config)
        self._active: object | None = None
        self._lock = RLock()

    @property
    def loaded(self) -> bool:
        return bool(self._active and getattr(self._active, "loaded", False))

    @property
    def active_language(self) -> str | None:
        return getattr(self._active, "last_detected_language", None)

    @property
    def detected_language(self) -> str | None:
        return self.active_language

    def load(self) -> None:
        with self._lock:
            self._activate(self._mongolian)

    def unload(self) -> None:
        with self._lock:
            for engine in (self._mongolian, self._english):
                engine.unload()
            self._active = None

    def _activate(self, engine: object) -> None:
        if self._active is engine:
            engine.load()
            return
        if self._active is not None:
            self._active.unload()
        engine.load()
        self._active = engine

    def transcribe(self, audio: str | Path, language: STTLanguage = "mn") -> str:
        with self._lock:
            if language == "mn":
                self._activate(self._mongolian)
                return self._mongolian.transcribe(audio, language="mn")
            if language == "en":
                self._activate(self._english)
                return self._english.transcribe(audio, language="en")
            # Qwen's language identifier is trustworthy for its supported English
            # class. Any other result is safely routed to the Mongolian model.
            self._activate(self._english)
            english_text = self._english.transcribe(audio, language="auto")
            if normalize_detected_language(getattr(self._english, "last_detected_language", None)) == "en":
                return english_text
            self._activate(self._mongolian)
            return self._mongolian.transcribe(audio, language="mn")
