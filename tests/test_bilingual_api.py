from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.core.config import load_config


def wav_bytes() -> bytes:
    buffer = BytesIO()
    sf.write(buffer, np.zeros(1600, dtype=np.float32), 16_000, format="WAV")
    return buffer.getvalue()


def test_default_mongolian_voice_uses_yesui_neural():
    config = load_config()

    assert config.tts_provider == "edge"
    assert config.tts_edge_voice == "mn-MN-YesuiNeural"


class RoutingSTT:
    loaded = False

    def __init__(self) -> None:
        self.languages: list[str | None] = []

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def transcribe(self, audio: str | Path, language: str | None = None) -> str:
        self.languages.append(language)
        return "Hello" if language == "en" else "Сайн байна уу"


class RoutingTTS:
    loaded = False

    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: list[tuple[str, str | None]] = []

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def voices(self) -> list[str]:
        return ["default"]

    def synthesize(self, text: str, speaker_id: str | None, output_path: Path) -> Path:
        self.calls.append((text, speaker_id))
        sf.write(output_path, np.zeros(1600, dtype=np.float32), 16_000, format="WAV")
        return output_path


class RoutingAgent:
    configured = True

    def respond(self, message: str) -> str:
        return f"reply: {message}"


def test_stt_routes_explicit_english_language():
    config = load_config()
    stt = RoutingSTT()
    tts = RoutingTTS("mn")
    client = TestClient(create_app(config, stt=stt, tts=tts, agent=RoutingAgent(), english_tts=RoutingTTS("en")))

    with client:
        response = client.post(
            "/stt",
            files={"file": ("input.wav", wav_bytes(), "audio/wav")},
            data={"language": "en"},
        )

    assert response.status_code == 200
    assert response.json() == {"transcript": "Hello"}
    assert stt.languages == ["en"]


def test_tts_routes_english_to_lazy_english_engine():
    config = load_config()
    mongolian_tts = RoutingTTS("mn")
    english_tts = RoutingTTS("en")
    client = TestClient(
        create_app(config, stt=RoutingSTT(), tts=mongolian_tts, agent=RoutingAgent(), english_tts=english_tts)
    )

    with client:
        response = client.post("/tts", json={"text": "Hello", "language": "en", "speaker_id": "ignored"})

    assert response.status_code == 200
    assert response.headers["x-voice-assistant-language"] == "en"
    assert english_tts.calls == [("Hello", "ignored")]
    assert mongolian_tts.calls == []


def test_health_reports_provider_without_exposing_key(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "secret-that-must-not-appear")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "test-model")
    config = load_config()
    client = TestClient(
        create_app(config, stt=RoutingSTT(), tts=RoutingTTS("mn"), agent=RoutingAgent(), english_tts=RoutingTTS("en"))
    )

    with client:
        response = client.get("/health")

    body = response.json()
    assert body["llm_provider"] == "nvidia_nim"
    assert body["llm_model"] == "test-model"
    assert body["llm_configured"] is True
    assert "secret-that-must-not-appear" not in response.text
