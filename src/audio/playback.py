from __future__ import annotations

import time
from typing import Protocol

import soundfile as sf

from src.audio.devices import AudioDevice
from src.core.config import AppConfig
from src.tts.engine import TTSEngine


class PlaybackError(RuntimeError):
    """Raised when synthesized audio cannot be sent to the selected output."""


class SpeakerPlayback(Protocol):
    """Playback contract used by the echo pipeline."""

    def speak(self, text: str, speaker_id: str | None = None) -> None:
        ...


class AudioPlayback:
    """Synthesize with TTS and play through a selected PortAudio output."""

    def __init__(self, config: AppConfig, device: AudioDevice, tts: TTSEngine | None = None) -> None:
        self.config = config
        self.device = device
        self.tts = tts or TTSEngine(config)
        self.last_audio_started_at: float | None = None
        self.last_audio_start_latency_seconds: float | None = None
        self.last_playback_seconds: float | None = None

    @staticmethod
    def _sounddevice():
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise PlaybackError("sounddevice is required for selectable speaker playback") from exc
        return sd

    def speak(self, text: str, speaker_id: str | None = None) -> None:
        output = self.tts.synthesize(text, speaker_id=speaker_id)
        started = time.perf_counter()
        try:
            audio, sample_rate = sf.read(output, dtype="float32", always_2d=False)
            sd = self._sounddevice()
            sd.play(audio, int(sample_rate), device=self.device.index)
            self.last_audio_started_at = time.perf_counter()
            self.last_audio_start_latency_seconds = self.last_audio_started_at - started
            sd.wait()
            self.last_playback_seconds = time.perf_counter() - started
        except Exception as exc:
            try:
                self._sounddevice().stop()
            except Exception:
                pass
            raise PlaybackError(f"Speaker playback failed on {self.device.label()}: {exc}") from exc
        finally:
            output.unlink(missing_ok=True)
