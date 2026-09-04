from pathlib import Path

from src.core.config import load_config
from src.stt.engine import STTEngine
from src.stt.router import STTLanguageRouter


class FakeEngine:
    def __init__(self, label: str) -> None:
        self.label = label
        self.loaded = False
        self.load_calls = 0
        self.unload_calls = 0
        self.transcribe_calls: list[tuple[Path, str | None]] = []

    def load(self) -> None:
        self.loaded = True
        self.load_calls += 1

    def unload(self) -> None:
        self.loaded = False
        self.unload_calls += 1

    def transcribe(self, audio: str | Path, language: str | None = None) -> str:
        self.transcribe_calls.append((Path(audio), language))
        return self.label


class FakeDetector(FakeEngine):
    def __init__(self, detected_language: str) -> None:
        super().__init__("detector")
        self.detected_language = detected_language
        self.detect_calls: list[Path] = []

    def detect_language(self, audio: str | Path) -> str:
        self.load()
        self.detect_calls.append(Path(audio))
        return self.detected_language


def test_router_swaps_active_language_model_and_routes_auto_language():
    config = load_config()
    mongolian = FakeEngine("mn transcript")
    english = FakeEngine("en transcript")
    detector = FakeDetector("en")
    router = STTLanguageRouter(
        config, mongolian=mongolian, english=english, detector=detector
    )

    router.load()
    assert router.transcribe("mn.wav", language="mn") == "mn transcript"
    assert router.transcribe("en.wav", language="en") == "en transcript"
    assert router.transcribe("en-again.wav", language="en") == "en transcript"
    assert router.transcribe("auto.wav", language="auto") == "en transcript"
    assert router.detected_language == "en"

    router.unload()
    assert detector.detect_calls == [Path("auto.wav")]
    assert detector.load_calls == 1
    assert detector.unload_calls == 2
    assert mongolian.load_calls == 1
    assert mongolian.unload_calls == 2
    assert english.load_calls == 1
    assert english.unload_calls == 1
    assert mongolian.transcribe_calls == [(Path("mn.wav"), "mn")]
    assert english.transcribe_calls == [
        (Path("en.wav"), "en"),
        (Path("en-again.wav"), "en"),
        (Path("auto.wav"), "en"),
    ]


def test_stt_engine_selects_language_specific_model_configuration():
    config = load_config()

    mongolian = STTEngine(config, language="mn")
    english = STTEngine(config, language="en")

    assert mongolian.model_id == config.stt_model_id
    assert mongolian.model_path == config.stt_local_path
    assert english.model_id == config.stt_english_model_id
    assert english.model_path == config.stt_english_local_path
