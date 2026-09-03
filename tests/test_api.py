from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from src.agent import AgentBridge
from src.api.server import create_app
from src.core.config import AppConfig, ConfigError, load_config


def wav_bytes() -> bytes:
    buffer = BytesIO()
    sf.write(buffer, np.zeros(1600, dtype=np.float32), 16_000, format="WAV")
    return buffer.getvalue()


class FakeSTT:
    def __init__(self) -> None:
        self.loaded = False
        self.calls: list[Path] = []
        self.load_calls = 0
        self.unload_calls = 0

    def load(self) -> None:
        self.load_calls += 1
        self.loaded = True

    def transcribe(self, audio: str | Path) -> str:
        path = Path(audio)
        self.calls.append(path)
        self.loaded = True
        return "Сайн байна уу?"

    def unload(self) -> None:
        self.unload_calls += 1
        self.loaded = False


class FakeTTS:
    def __init__(self) -> None:
        self.loaded = False
        self.calls: list[tuple[str, str | None]] = []
        self.load_calls = 0
        self.unload_calls = 0

    def load(self) -> None:
        self.load_calls += 1
        self.loaded = True

    def voices(self) -> list[str]:
        self.loaded = True
        return ["spk_0000", "spk_0064"]

    def synthesize(self, text: str, speaker_id: str | None, output_path: Path) -> Path:
        self.loaded = True
        self.calls.append((text, speaker_id))
        sf.write(output_path, np.zeros(1600, dtype=np.float32), 16_000, format="WAV")
        return output_path

    def unload(self) -> None:
        self.unload_calls += 1
        self.loaded = False


class FakeAgent:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def respond(self, message: str) -> str:
        self.messages.append(message)
        return message


def make_client() -> tuple[TestClient, FakeSTT, FakeTTS, FakeAgent]:
    config = load_config()
    stt = FakeSTT()
    tts = FakeTTS()
    agent = FakeAgent()
    assert isinstance(agent, AgentBridge)
    return TestClient(create_app(config, stt=stt, tts=tts, agent=agent)), stt, tts, agent


def test_api_exposes_health_and_localhost_security_boundary():
    client, _, _, _ = make_client()

    with client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["bind_host"] == "127.0.0.1"
    assert response.json()["external_network_exposure"] is False
    assert response.json()["stt_loaded"] is True
    assert response.json()["tts_loaded"] is True


def test_api_preloads_each_engine_once_for_a_lifespan():
    client, stt, tts, _ = make_client()

    with client:
        assert stt.load_calls == 1
        assert tts.load_calls == 1

    assert stt.unload_calls == 1
    assert tts.unload_calls == 1


def test_api_lists_voices_without_recreating_tts_engine():
    client, _, tts, _ = make_client()

    with client:
        response = client.get("/voices")

    assert response.status_code == 200
    assert response.json() == {"voices": ["spk_0000", "spk_0064"], "count": 2}
    assert tts.load_calls == 1


def test_api_transcribes_uploaded_audio_and_removes_temporary_file():
    client, stt, _, _ = make_client()

    with client:
        response = client.post(
            "/stt",
            files={"file": ("input.wav", wav_bytes(), "audio/wav")},
        )

    assert response.status_code == 200
    assert response.json() == {"transcript": "Сайн байна уу?"}
    assert len(stt.calls) == 1
    assert not stt.calls[0].exists()


def test_api_returns_generated_wav_for_tts():
    client, _, tts, _ = make_client()

    with client:
        response = client.post("/tts", json={"text": "Сайн байна уу", "speaker_id": "spk_0064"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    audio_info = sf.info(BytesIO(response.content))
    assert audio_info.samplerate == 16_000
    assert audio_info.frames == 1600
    assert tts.calls == [("Сайн байна уу", "spk_0064")]


def test_api_chat_uses_agent_bridge_after_text_normalization():
    client, _, _, agent = make_client()

    with client:
        response = client.post("/chat", json={"message": "  Сайн   байна уу?  "})

    assert response.status_code == 200
    assert response.json() == {
        "message": "Сайн байна уу?",
        "response": "Сайн байна уу?",
    }
    assert agent.messages == ["Сайн байна уу?"]


def test_api_rejects_oversized_upload():
    config = load_config()
    data = deepcopy(config.data)
    data["api"]["max_upload_bytes"] = 4
    small_limit_config = AppConfig(path=config.path, data=data)
    small_limit_config.validate()
    client = TestClient(create_app(small_limit_config, stt=FakeSTT(), tts=FakeTTS(), agent=FakeAgent()))

    with client:
        response = client.post("/stt", files={"file": ("input.wav", b"12345", "audio/wav")})

    assert response.status_code == 413


def test_config_rejects_non_loopback_api_host():
    config = load_config()
    data = deepcopy(config.data)
    data["api"]["host"] = "0.0.0.0"

    with pytest.raises(ConfigError, match="localhost only"):
        AppConfig(path=config.path, data=data).validate()
