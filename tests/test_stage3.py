from __future__ import annotations

import numpy as np
import pytest

from src.agent import EchoAgent
from src.audio import AudioCaptureError, AudioGate, VADConfig, VoiceActivityDetector
from src.audio.capture import Recording
from src.audio.devices import AudioDevice, AudioDeviceManager
from src.pipeline import AssistantState, EchoPipeline
from src.text import TextNormalizer


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
        self.calls = 0

    def record(self) -> Recording:
        self.calls += 1
        return self.recording


class FakeSTT:
    last_latency_seconds = 0.25

    def __init__(self) -> None:
        self.samples = []

    def transcribe(self, samples: np.ndarray) -> str:
        self.samples.append(samples)
        return "  Сайн   байна уу?  "


class FakeTTS:
    last_synthesis_seconds = 0.4


class FakePlayback:
    def __init__(self) -> None:
        self.tts = FakeTTS()
        self.last_audio_started_at = None
        self.calls: list[tuple[str, str | None]] = []
        self.gate = None

    def speak(self, text: str, speaker_id: str | None = None) -> None:
        if self.gate is not None:
            assert not self.gate.listening_allowed
        self.calls.append((text, speaker_id))
        self.last_audio_started_at = 11.8


def test_audio_device_resolution_supports_case_insensitive_name():
    devices = [
        INPUT,
        AudioDevice(3, "Headphones", "MME", 0, 2, 44_100),
    ]

    selected = AudioDeviceManager._resolve_configured("microphone array", devices, "input")

    assert selected == INPUT


def test_vad_starts_on_speech_and_ends_after_configured_silence():
    detector = VoiceActivityDetector(
        VADConfig(start_threshold=0.5, stop_threshold=0.2, silence_seconds=0.1, min_speech_seconds=0.1)
    )

    assert not detector.process(np.zeros(1600, dtype=np.float32), now=0.0)
    assert not detector.process(np.ones(1600, dtype=np.float32) * 0.6, now=0.1)
    assert detector.speech_started
    assert not detector.process(np.zeros(1600, dtype=np.float32), now=0.15)
    assert detector.process(np.zeros(1600, dtype=np.float32), now=0.25)
    assert detector.meets_minimum_duration(16_000)


def test_vad_rejects_inverted_thresholds():
    with pytest.raises(AudioCaptureError, match="stop threshold"):
        VADConfig(start_threshold=0.01, stop_threshold=0.02, silence_seconds=0.8, min_speech_seconds=0.25)


def test_audio_gate_blocks_listening_only_during_playback():
    gate = AudioGate()

    assert gate.listening_allowed
    with gate.speaking():
        assert not gate.listening_allowed
    assert gate.listening_allowed


def test_normalizer_only_collapses_whitespace():
    assert TextNormalizer().normalize("  Монгол\tхэлээр   ярьж байна.  ") == "Монгол хэлээр ярьж байна."


def test_echo_pipeline_runs_required_state_sequence_and_returns_idle():
    stt = FakeSTT()
    playback = FakePlayback()
    gate = AudioGate()
    playback.gate = gate
    pipeline = EchoPipeline(FakeRecorder(), stt, agent=EchoAgent(), playback=playback, gate=gate)

    turn = pipeline.echo_once(speaker_id="spk_0064")

    assert stt.samples
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
    assert gate.listening_allowed
    assert turn.stt_latency_seconds == 0.25
    assert turn.tts_latency_seconds == 0.4
    assert turn.end_of_speech_to_audio_start_seconds == pytest.approx(0.8)


def test_three_consecutive_turns_reuse_the_same_pipeline_and_return_idle():
    recorder = FakeRecorder()
    stt = FakeSTT()
    playback = FakePlayback()
    pipeline = EchoPipeline(recorder, stt, agent=EchoAgent(), playback=playback)

    turns = [pipeline.echo_once() for _ in range(3)]

    assert len(turns) == 3
    assert recorder.calls == 3
    assert len(stt.samples) == 3
    assert len(playback.calls) == 3
    assert pipeline.state is AssistantState.IDLE


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
