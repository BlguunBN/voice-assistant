from __future__ import annotations

import numpy as np
import pytest

from src.agent import EchoAgent
from src.audio.capture import Recording
from src.audio.devices import AudioDevice, AudioDeviceManager
from src.pipeline import AssistantState, EchoPipeline


INPUT = AudioDevice(1, "Microphone Array", "MME", 2, 0, 16_000)


class FakeRecorder:
    def __init__(self) -> None:
        self.recording = Recording(
            samples=np.zeros(16_000, dtype=np.float32),
            sample_rate=16_000,
            started_at=10.0,
            ended_at=11.0,
            device=INPUT,
        )

    def record_push_to_talk(self) -> Recording:
        return self.recording


class FakeSTT:
    last_latency_seconds = 0.25

    def __init__(self) -> None:
        self.samples = None

    def transcribe(self, samples: np.ndarray) -> str:
        self.samples = samples
        return "Сайн байна уу?"


class FakeTTS:
    last_synthesis_seconds = 0.4


class FakePlayback:
    def __init__(self) -> None:
        self.tts = FakeTTS()
        self.last_audio_started_at = None
        self.calls: list[tuple[str, str | None]] = []

    def speak(self, text: str, speaker_id: str | None = None) -> None:
        self.calls.append((text, speaker_id))
        self.last_audio_started_at = 11.8


def test_audio_device_resolution_supports_case_insensitive_name():
    devices = [
        INPUT,
        AudioDevice(3, "Headphones", "MME", 0, 2, 44_100),
    ]

    selected = AudioDeviceManager._resolve_configured("microphone array", devices, "input")

    assert selected == INPUT


def test_echo_pipeline_runs_required_state_sequence_and_returns_idle():
    stt = FakeSTT()
    playback = FakePlayback()
    pipeline = EchoPipeline(FakeRecorder(), stt, agent=EchoAgent(), playback=playback)

    turn = pipeline.echo_once(speaker_id="spk_0064")

    assert stt.samples is not None
    assert turn.transcript == "Сайн байна уу?"
    assert turn.response == "Сайн байна уу?"
    assert playback.calls == [("Сайн байна уу?", "spk_0064")]
    assert turn.state_transitions == (
        AssistantState.IDLE,
        AssistantState.LISTENING,
        AssistantState.TRANSCRIBING,
        AssistantState.THINKING,
        AssistantState.SPEAKING,
        AssistantState.IDLE,
    )
    assert pipeline.state is AssistantState.IDLE
    assert turn.stt_latency_seconds == 0.25
    assert turn.tts_latency_seconds == 0.4
    assert turn.end_of_speech_to_audio_start_seconds == pytest.approx(0.8)


def test_listen_once_does_not_speak():
    playback = FakePlayback()
    pipeline = EchoPipeline(FakeRecorder(), FakeSTT(), agent=EchoAgent(), playback=playback)

    _, transcript, transitions = pipeline.listen_once()

    assert transcript == "Сайн байна уу?"
    assert playback.calls == []
    assert transitions == (
        AssistantState.IDLE,
        AssistantState.LISTENING,
        AssistantState.TRANSCRIBING,
        AssistantState.IDLE,
    )
