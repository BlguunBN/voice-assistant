from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.agent.echo import EchoAgent
from src.audio.capture import AudioRecorder, Recording
from src.audio.playback import SpeakerPlayback
from src.stt.engine import STTEngine


class AssistantState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


@dataclass(frozen=True)
class EchoTurn:
    """Evidence from one microphone-to-speaker turn."""

    recording: Recording
    transcript: str
    response: str
    stt_latency_seconds: float | None
    tts_latency_seconds: float | None
    end_of_speech_to_audio_start_seconds: float | None
    state_transitions: tuple[AssistantState, ...]


class EchoPipeline:
    """Run one-shot push-to-talk STT → EchoAgent → TTS turns."""

    _allowed_transitions = {
        AssistantState.IDLE: {AssistantState.LISTENING},
        AssistantState.LISTENING: {AssistantState.TRANSCRIBING},
        AssistantState.TRANSCRIBING: {AssistantState.THINKING, AssistantState.IDLE},
        AssistantState.THINKING: {AssistantState.SPEAKING, AssistantState.IDLE},
        AssistantState.SPEAKING: {AssistantState.IDLE},
    }

    def __init__(
        self,
        recorder: AudioRecorder,
        stt: STTEngine,
        agent: EchoAgent,
        playback: SpeakerPlayback,
    ) -> None:
        self.recorder = recorder
        self.stt = stt
        self.agent = agent
        self.playback = playback
        self.state = AssistantState.IDLE
        self.transitions: list[AssistantState] = [self.state]

    def _transition(self, next_state: AssistantState) -> None:
        if next_state not in self._allowed_transitions[self.state]:
            raise RuntimeError(f"Invalid assistant transition: {self.state} -> {next_state}")
        self.state = next_state
        self.transitions.append(next_state)

    def _reset_after_error(self) -> None:
        if self.state != AssistantState.IDLE:
            self.state = AssistantState.IDLE
            self.transitions.append(AssistantState.IDLE)

    def _capture_and_transcribe(self) -> tuple[Recording, str]:
        self._transition(AssistantState.LISTENING)
        try:
            recording = self.recorder.record_push_to_talk()
            self._transition(AssistantState.TRANSCRIBING)
            transcript = self.stt.transcribe(recording.samples)
            return recording, transcript
        except Exception:
            self._reset_after_error()
            raise

    def listen_once(self) -> tuple[Recording, str, tuple[AssistantState, ...]]:
        """Capture and transcribe one turn without speaking a response."""
        self.transitions = [AssistantState.IDLE]
        recording, transcript = self._capture_and_transcribe()
        self._transition(AssistantState.IDLE)
        return recording, transcript, tuple(self.transitions)

    def echo_once(self, speaker_id: str | None = None) -> EchoTurn:
        """Capture, transcribe, echo, synthesize, play, and return to IDLE."""
        self.transitions = [AssistantState.IDLE]
        recording, transcript = self._capture_and_transcribe()
        try:
            self._transition(AssistantState.THINKING)
            response = self.agent.respond(transcript)
            self._transition(AssistantState.SPEAKING)
            audio_start_before = getattr(self.playback, "last_audio_started_at", None)
            self.playback.speak(response, speaker_id=speaker_id)
            audio_start_at = getattr(self.playback, "last_audio_started_at", None)
            if audio_start_at is None:
                audio_start_at = audio_start_before
            self._transition(AssistantState.IDLE)
            tts_engine: Any = getattr(self.playback, "tts", None)
            tts_latency = getattr(tts_engine, "last_synthesis_seconds", None)
            start_latency = (
                audio_start_at - recording.ended_at
                if audio_start_at is not None
                else None
            )
            return EchoTurn(
                recording=recording,
                transcript=transcript,
                response=response,
                stt_latency_seconds=self.stt.last_latency_seconds,
                tts_latency_seconds=tts_latency,
                end_of_speech_to_audio_start_seconds=start_latency,
                state_transitions=tuple(self.transitions),
            )
        except Exception:
            self._reset_after_error()
            raise
