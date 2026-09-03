from __future__ import annotations

from dataclasses import dataclass
import ctypes
import logging
import threading
import time
from typing import Any, Callable

import numpy as np

from src.audio.devices import AudioDevice


LOGGER = logging.getLogger(__name__)


class AudioCaptureError(RuntimeError):
    """Raised when microphone capture cannot start or produce usable audio."""


@dataclass(frozen=True)
class VADConfig:
    """Energy-based voice activity detection thresholds and timing limits."""

    start_threshold: float
    stop_threshold: float
    silence_seconds: float
    min_speech_seconds: float

    def __post_init__(self) -> None:
        if self.start_threshold <= 0 or self.stop_threshold <= 0:
            raise AudioCaptureError("VAD thresholds must be positive")
        if self.stop_threshold > self.start_threshold:
            raise AudioCaptureError("VAD stop threshold must not exceed start threshold")
        if self.silence_seconds <= 0 or self.min_speech_seconds <= 0:
            raise AudioCaptureError("VAD timing values must be positive")


class VoiceActivityDetector:
    """Frame-energy VAD with separate start and stop thresholds."""

    def __init__(self, config: VADConfig) -> None:
        self.config = config
        self.speech_started_at: float | None = None
        self.last_voice_at: float | None = None
        self.speech_frames = 0

    @staticmethod
    def _rms(samples: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))

    @property
    def speech_started(self) -> bool:
        return self.speech_started_at is not None


    def process(self, samples: np.ndarray, now: float) -> bool:
        """Consume one mono frame and return whether trailing silence ended speech."""
        level = self._rms(samples)
        if not self.speech_started:
            if level >= self.config.start_threshold:
                self.speech_started_at = now
                self.last_voice_at = now
                self.speech_frames += samples.size
            return False
        if level >= self.config.stop_threshold:
            self.last_voice_at = now
            self.speech_frames += samples.size
            return False
        if self.last_voice_at is not None and now - self.last_voice_at >= self.config.silence_seconds:
            return True
        return False

    def meets_minimum_duration(self, sample_rate: int) -> bool:
        return self.speech_frames / sample_rate >= self.config.min_speech_seconds


@dataclass(frozen=True)
class Recording:
    """One push-to-talk recording and its timing evidence."""

    samples: np.ndarray
    sample_rate: int
    started_at: float
    ended_at: float
    device: AudioDevice

    @property
    def duration_seconds(self) -> float:
        return self.samples.shape[0] / self.sample_rate


class AudioRecorder:
    """Capture one utterance while the configured Windows hotkey is held."""

    def __init__(
        self,
        device: AudioDevice,
        sample_rate: int,
        max_seconds: float,
        blocksize: int,
        hotkey: str = "space",
        poll_interval_seconds: float = 0.01,
        vad: VADConfig | None = None,
        gate: Any = None,
        stream_factory: Callable[..., Any] | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise AudioCaptureError("Audio sample rate must be positive")
        if max_seconds <= 0:
            raise AudioCaptureError("Maximum recording duration must be positive")
        if blocksize <= 0:
            raise AudioCaptureError("Audio block size must be positive")
        if hotkey.lower() != "space":
            raise AudioCaptureError("Stage 3 and 4 support the 'space' push-to-talk hotkey")
        self.device = device
        self.sample_rate = sample_rate
        self.max_seconds = max_seconds
        self.blocksize = blocksize
        self.hotkey = hotkey.lower()
        self.poll_interval_seconds = poll_interval_seconds
        self.vad = vad
        self.gate = gate
        self._stream_factory = stream_factory

    @staticmethod
    def _sounddevice() -> Any:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioCaptureError("sounddevice is required for microphone capture") from exc
        return sd

    def _stream(self, callback: Callable[..., None]) -> Any:
        factory = self._stream_factory or self._sounddevice().InputStream
        return factory(
            samplerate=self.sample_rate,
            device=self.device.index,
            channels=1,
            dtype="float32",
            blocksize=self.blocksize,
            callback=callback,
        )

    @staticmethod
    def _space_is_down() -> bool:
        if not hasattr(ctypes, "windll"):
            raise AudioCaptureError("Push-to-talk requires Windows keyboard polling")
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x20) & 0x8000)

    def _ensure_listening_allowed(self) -> None:
        if self.gate is not None and not self.gate.listening_allowed:
            raise AudioCaptureError("Microphone capture is paused while the assistant is speaking")

    def _wait_for_release(self) -> None:
        while self._space_is_down():
            time.sleep(self.poll_interval_seconds)

    def _wait_for_press(self) -> None:
        while not self._space_is_down():
            time.sleep(self.poll_interval_seconds)

    def record_push_to_talk(self) -> Recording:
        """Wait for Space, capture while held, and return a mono float32 waveform."""
        return self._record(stop_on_silence=False)

    def record(self) -> Recording:
        """Capture one turn using VAD when configured, otherwise key-release PTT."""
        if self.vad is not None:
            return self.record_with_vad()
        return self.record_push_to_talk()

    def record_with_vad(self) -> Recording:
        """Wait for Space, then stop after speech and configured trailing silence."""
        if self.vad is None:
            raise AudioCaptureError("VAD is not configured")
        return self._record(stop_on_silence=True)

    def _record(self, stop_on_silence: bool) -> Recording:
        self._ensure_listening_allowed()
        chunks: list[np.ndarray] = []
        callback_status: list[str] = []
        detector = VoiceActivityDetector(self.vad) if stop_on_silence and self.vad else None
        done = threading.Event()

        def callback(indata: np.ndarray, frames: int, callback_time: Any, status: Any) -> None:
            del frames, callback_time
            if status:
                callback_status.append(str(status))
            chunk = indata[:, 0].copy()
            chunks.append(chunk)
            if detector is not None and detector.process(chunk, time.perf_counter()):
                done.set()

        try:
            self._wait_for_release()
            mode = "with VAD" if stop_on_silence else "until key release"
            print(f"Hold {self.hotkey.upper()} to record {mode}; release it to transcribe.")
            self._wait_for_press()
            started_at = time.perf_counter()
            with self._stream(callback):
                while self._space_is_down():
                    elapsed = time.perf_counter() - started_at
                    if elapsed >= self.max_seconds or (detector is not None and done.is_set()):
                        break
                    time.sleep(self.poll_interval_seconds)
            ended_at = time.perf_counter()
        except AudioCaptureError:
            raise
        except Exception as exc:
            raise AudioCaptureError(f"Microphone capture failed: {exc}") from exc

        if callback_status:
            LOGGER.warning("Microphone stream status: %s", "; ".join(callback_status))
        if not chunks:
            raise AudioCaptureError("Microphone returned no audio frames")
        samples = np.concatenate(chunks).astype(np.float32, copy=False)
        if samples.size == 0:
            raise AudioCaptureError("Microphone returned an empty recording")
        if detector is not None:
            if not detector.speech_started:
                raise AudioCaptureError("No speech detected; transcription was skipped")
            if not detector.meets_minimum_duration(self.sample_rate):
                raise AudioCaptureError("Speech was shorter than the configured minimum")
        LOGGER.info(
            "Captured %.3f seconds from input=%s mode=%s",
            samples.size / self.sample_rate,
            self.device.label(),
            "vad" if detector is not None else "push_to_talk",
        )
        return Recording(
            samples=samples,
            sample_rate=self.sample_rate,
            started_at=started_at,
            ended_at=ended_at,
            device=self.device,
        )
