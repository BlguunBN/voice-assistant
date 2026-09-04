from __future__ import annotations

from pathlib import Path
import re
from threading import RLock
from typing import Literal

from src.core.config import AppConfig

from .engine import STTEngine, STTError


STTLanguage = Literal["mn", "en", "auto"]

_LANGUAGE_HINT_WORDS = {
    "en": frozenset(
        {
            "a", "an", "and", "are", "can", "do", "for", "from", "have", "hello",
            "help", "how", "i", "is", "it", "me", "my", "of", "on", "please", "the",
            "this", "to", "we", "what", "with", "you", "your",
        }
    ),
    "mn": frozenset(
        {
            "\u0431\u0430\u0439\u043d\u0430", "\u0431\u0430\u044f\u0440\u043b\u0430\u043b\u0430\u0430", "\u0431\u0438", "\u0431\u043e\u043b", "\u0445\u0430\u0430\u043d\u0430", "\u0445\u044d\u0440\u0445\u044d\u043d", "\u043c\u0438\u043d\u0438\u0439", "\u0441\u0430\u0439\u043d",
            "\u0442\u0430", "\u0442\u0430\u043d\u0434", "\u0442\u0430\u043d\u044b", "\u0442\u0443\u0441\u043b\u0430\u0430\u0447", "\u0442\u044d\u0440", "\u0443\u0443", "\u044d\u043d\u044d", "\u0447\u0438\u043d\u0438\u0439", "\u044e\u0443",
        }
    ),
}


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

    @staticmethod
    def _language_evidence(text: str, language: str) -> float:
        """Score whether a transcript looks like its requested output language."""
        letters = [character for character in text if character.isalpha()]
        if not letters:
            return 0.0
        cyrillic_ratio = sum("\u0400" <= character <= "\u052f" for character in letters) / len(letters)
        latin_ratio = sum(character.isascii() and character.isalpha() for character in letters) / len(letters)
        script_ratio = cyrillic_ratio if language == "mn" else latin_ratio
        words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
        hint_word_ratio = (
            sum(word in _LANGUAGE_HINT_WORDS[language] for word in words) / len(words)
            if words
            else 0.0
        )
        return script_ratio * (0.7 + 0.3 * hint_word_ratio)

    def _detected_candidate(self, audio: str | Path) -> str | None:
        """Use the lightweight detector only when transcript evidence is inconclusive."""
        try:
            detected = self._detector.detect_language(audio)
        except Exception:
            return None
        finally:
            self._detector.unload()
        return detected if detected in self._engines else None

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
                candidates: list[tuple[str, str, float]] = []
                errors: list[tuple[str, Exception]] = []
                for candidate_language in ("mn", "en"):
                    try:
                        engine = self._activate(candidate_language)
                        text = engine.transcribe(audio, language=candidate_language)
                    except Exception as exc:
                        errors.append((candidate_language, exc))
                        continue
                    candidates.append(
                        (
                            candidate_language,
                            text,
                            self._language_evidence(text, candidate_language),
                        )
                    )

                if not candidates:
                    details = "; ".join(
                        f"{candidate_language}: {error}"
                        for candidate_language, error in errors
                    )
                    raise STTError(f"Auto STT failed for Mongolian and English: {details}")

                candidates.sort(key=lambda candidate: candidate[2], reverse=True)
                detected, text, strongest_evidence = candidates[0]
                if (
                    len(candidates) > 1
                    and strongest_evidence - candidates[1][2] < 0.15
                ):
                    detector_language = self._detected_candidate(audio)
                    if detector_language is not None:
                        detected, text, _evidence = next(
                            candidate
                            for candidate in candidates
                            if candidate[0] == detector_language
                        )
                self._detected_language = detected
                if self._active_language != detected:
                    self._activate(detected)
                return text

            selected = self._select(language)
            engine = self._activate(selected)
            self._detected_language = selected
            return engine.transcribe(audio, language=selected)
