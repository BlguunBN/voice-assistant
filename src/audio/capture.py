from __future__ import annotations

from dataclasses import dataclass
import ctypes
import logging
import time
from typing import Any, Callable

import numpy as np

from src.audio.devices import AudioDevice


LOGGER = logging.getLogger(__name__)


class AudioCaptureError(RuntimeError):
    """Raised when microphone capture cannot start or produce audio."""


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
        stream_factory: Callable[..., Any] | None = None,
    ) -> None:
        if sample_rate <= 0:
            raise AudioCaptureError("Audio sample rate must be positive")
        if max_seconds <= 0:
            raise AudioCaptureError("Maximum recording duration must be positive")
        if blocksize <= 0:
            raise AudioCaptureError("Audio block size must be positive")
        if hotkey.lower() != "space":
            raise AudioCaptureError("Stage 3 supports the 'space' push-to-talk hotkey")
        self.device = device
        self.sample_rate = sample_rate
        self.max_seconds = max_seconds
        self.blocksize = blocksize
        self.hotkey = hotkey.lower()
        self.poll_interval_seconds = poll_interval_seconds
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

    def _wait_for_release(self) -> None:
        while self._space_is_down():
            time.sleep(self.poll_interval_seconds)

    def _wait_for_press(self) -> None:
        while not self._space_is_down():
            time.sleep(self.poll_interval_seconds)

    def record_push_to_talk(self) -> Recording:
        """Wait for Space, capture while held, and return a mono float32 waveform."""
        chunks: list[np.ndarray] = []
        callback_status: list[str] = []

        def callback(indata: np.ndarray, frames: int, callback_time: Any, status: Any) -> None:
            del frames, callback_time
            if status:
                callback_status.append(str(status))
            chunks.append(indata[:, 0].copy())

        try:
            self._wait_for_release()
            print(f"Hold {self.hotkey.upper()} to record; release it to transcribe.")
            self._wait_for_press()
            started_at = time.perf_counter()
            with self._stream(callback):
                while self._space_is_down():
                    if time.perf_counter() - started_at >= self.max_seconds:
                        LOGGER.warning("Maximum recording duration reached: %.1f seconds", self.max_seconds)
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
        LOGGER.info(
            "Captured %.3f seconds from input=%s",
            samples.size / self.sample_rate,
            self.device.label(),
        )
        return Recording(
            samples=samples,
            sample_rate=self.sample_rate,
            started_at=started_at,
            ended_at=ended_at,
            device=self.device,
        )
