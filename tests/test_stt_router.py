from pathlib import Path

from src.core.config import load_config
from src.stt.router import STTLanguageRouter


class FakeEngine:
    loaded = False
    last_detected_language = None

    def __init__(self) -> None:
        self.load_calls = self.unload_calls = 0
        self.languages: list[str] = []

    def load(self) -> None:
        self.loaded = True
        self.load_calls += 1

    def unload(self) -> None:
        self.loaded = False
        self.unload_calls += 1

    def transcribe(self, _audio: Path, *, language: str) -> str:
        self.languages.append(language)
        self.last_detected_language = "English" if language == "auto" else language
        return "Hello" if language in {"en", "auto"} else "Сайн байна уу"


def test_router_routes_explicit_languages_and_keeps_only_one_engine_resident():
    mongolian, english = FakeEngine(), FakeEngine()
    router = STTLanguageRouter(load_config(), mongolian_engine=mongolian, english_engine=english)
    router.load()
    assert router.transcribe("mn.wav", language="mn") == "Сайн байна уу"
    assert router.transcribe("en.wav", language="en") == "Hello"
    assert mongolian.languages == ["mn"]
    assert english.languages == ["en"]
    assert mongolian.unload_calls == 1
    assert router.detected_language == "en"
    router.unload()
    assert english.unload_calls == 1


def test_router_auto_returns_qwen_english_or_falls_back_to_mongolian():
    mongolian, english = FakeEngine(), FakeEngine()
    router = STTLanguageRouter(load_config(), mongolian_engine=mongolian, english_engine=english)
    assert router.transcribe("auto.wav", language="auto") == "Hello"
    assert english.languages == ["auto"]
    assert mongolian.languages == []
