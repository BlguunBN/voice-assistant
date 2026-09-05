"""Mongolian speech-to-text engines."""

from .engine import STTError, STTEngine
from .language import STTLanguage
from .router import STTLanguageRouter

__all__ = ["STTError", "STTEngine", "STTLanguage", "STTLanguageRouter"]
