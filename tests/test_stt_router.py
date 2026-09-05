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
        self.last_detected_language = "en" if language == "auto" else language
        return "Hello" if self.last_detected_language == "en" else "Сайн байна уу"


def test_router_uses_one_engine_for_every_language_and_keeps_it_resident():
    engine = FakeEngine()
    router = STTLanguageRouter(load_config(), engine=engine)
    router.load()
    assert router.transcribe("mn.wav", language="mn") == "Сайн байна уу"
    assert router.transcribe("en.wav", language="en") == "Hello"
    assert router.transcribe("auto.wav", language="auto") == "Hello"
    assert engine.load_calls == 1
    assert engine.languages == ["mn", "en", "auto"]
    assert router.detected_language == "en"
    router.unload()
    assert engine.unload_calls == 1
