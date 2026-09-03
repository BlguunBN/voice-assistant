from __future__ import annotations

from collections.abc import Mapping
import gc
import logging
import os
from pathlib import Path
import time
from typing import Any

import numpy as np
import soundfile as sf

from src.core.config import AppConfig


LOGGER = logging.getLogger(__name__)


class STTError(RuntimeError):
    """Raised when loading or running the speech-to-text engine fails."""


class STTEngine:
    """Local Whisper speech-to-text engine with CUDA and CPU fallback."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.device = "cpu"
        self.loaded = False
        self.load_time_seconds: float | None = None
        self.last_latency_seconds: float | None = None
        self.last_audio_duration_seconds: float | None = None
        self.last_peak_vram_bytes: int | None = None
        self._processor: Any = None
        self._model: Any = None
        self._forced_device: str | None = None

    @property
    def model_path(self) -> Path:
        return self.config.stt_local_path

    def _choose_device(self) -> str:
        requested = self._forced_device or self.config.stt_device
        if requested == "cpu":
            return "cpu"
        if requested == "cuda":
            import torch

            if torch.cuda.is_available():
                return "cuda"
            fallback = self.config.stt_fallback_device
            if fallback == "cpu":
                LOGGER.warning("CUDA is unavailable; using configured CPU fallback")
                return "cpu"
            raise STTError("CUDA is unavailable and no usable fallback device is configured")
        raise STTError(f"Unsupported STT device: {requested}")

    def load(self) -> None:
        """Load the processor and model once, keeping them resident for requests."""
        if self.loaded:
            return
        if not self.model_path.is_dir():
            raise STTError(
                f"STT model is not installed at {self.model_path}. "
                f"Download {self.config.stt_model_id} into that directory first."
            )

        started = time.perf_counter()
        try:
            import torch
            from transformers import AutoProcessor, WhisperForConditionalGeneration

            self.device = self._choose_device()
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            self._processor = AutoProcessor.from_pretrained(
                str(self.model_path),
                local_files_only=True,
                extra_special_tokens={},
            )
            self._model = WhisperForConditionalGeneration.from_pretrained(
                str(self.model_path),
                local_files_only=True,
                dtype=dtype,
            )
            self._model.to(self.device)
            self._model.eval()
            self.loaded = True
            self.load_time_seconds = time.perf_counter() - started
            LOGGER.info(
                "Loaded STT model=%s device=%s load_seconds=%.3f",
                self.config.stt_model_id,
                self.device,
                self.load_time_seconds,
            )
        except STTError:
            raise
        except Exception as exc:
            self.unload()
            raise STTError(f"Unable to load STT model: {exc}") from exc

    def unload(self) -> None:
        """Release model resources and clear CUDA allocations when available."""
        self._processor = None
        self._model = None
        self.loaded = False
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @staticmethod
    def _resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if source_rate == target_rate:
            return audio.astype(np.float32, copy=False)
        if audio.size == 0:
            return audio.astype(np.float32)
        target_length = max(1, round(audio.size * target_rate / source_rate))
        source_positions = np.linspace(0, audio.size - 1, num=audio.size)
        target_positions = np.linspace(0, audio.size - 1, num=target_length)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)

    def _read_audio(self, audio: str | os.PathLike[str] | np.ndarray) -> np.ndarray:
        if isinstance(audio, (str, os.PathLike)):
            path = Path(audio)
            if not path.is_file():
                raise STTError(f"Audio file not found: {path}")
            try:
                samples, sample_rate = sf.read(path, dtype="float32", always_2d=False)
            except Exception as exc:
                raise STTError(f"Unable to read WAV/audio file {path}: {exc}") from exc
            array = np.asarray(samples, dtype=np.float32)
            if array.ndim == 2:
                array = array.mean(axis=1)
            source_rate = int(sample_rate)
        else:
            array = np.asarray(audio, dtype=np.float32)
            if array.ndim == 2:
                array = array.mean(axis=1)
            source_rate = self.config.stt_sample_rate

        if array.ndim != 1 or array.size == 0:
            raise STTError("Audio must contain a non-empty mono or multi-channel waveform")
        if not np.isfinite(array).all():
            raise STTError("Audio contains NaN or infinite samples")
        return self._resample(array, source_rate, self.config.stt_sample_rate)

    @staticmethod
    def _move_inputs(
        inputs: Mapping[str, Any], device: str, dtype: Any = None
    ) -> dict[str, Any]:
        moved: dict[str, Any] = {}
        for key, value in inputs.items():
            if hasattr(value, "to"):
                if dtype is not None and getattr(value, "is_floating_point", lambda: False)():
                    moved[key] = value.to(device=device, dtype=dtype)
                else:
                    moved[key] = value.to(device)
            else:
                moved[key] = value
        return moved

    def _transcribe_loaded(self, audio: np.ndarray) -> str:
        import torch

        inputs = self._processor(
            audio,
            sampling_rate=self.config.stt_sample_rate,
            return_tensors="pt",
            return_attention_mask=True,
        )
        model_inputs = self._move_inputs(
            inputs, self.device, getattr(self._model, "dtype", None)
        )
        if self.device == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            generated_ids = self._model.generate(
                **model_inputs,
                language="mn",
                task="transcribe",
                max_new_tokens=self.config.stt_max_new_tokens,
            )
        if self.device == "cuda":
            torch.cuda.synchronize()
        self.last_latency_seconds = time.perf_counter() - started
        if self.device == "cuda":
            self.last_peak_vram_bytes = int(torch.cuda.max_memory_allocated())
        text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        result = str(text).strip()
        if not result:
            raise STTError("STT returned empty text")
        LOGGER.info(
            "STT latency_seconds=%.3f audio_seconds=%.3f text=%r",
            self.last_latency_seconds,
            self.last_audio_duration_seconds or 0.0,
            result,
        )
        return result

    def transcribe(self, audio: str | os.PathLike[str] | np.ndarray) -> str:
        """Transcribe a local audio file or 16 kHz waveform into text."""
        self.load()
        samples = self._read_audio(audio)
        self.last_audio_duration_seconds = samples.size / self.config.stt_sample_rate
        if self.device == "cuda":
            import torch

            torch.cuda.reset_peak_memory_stats()
        try:
            return self._transcribe_loaded(samples)
        except RuntimeError as exc:
            if self.device != "cuda" or "out of memory" not in str(exc).lower():
                raise STTError(f"STT inference failed: {exc}") from exc
            LOGGER.exception("CUDA out of memory during STT; retrying on CPU")
            self.unload()
            self._forced_device = "cpu"
            self.load()
            return self._transcribe_loaded(samples)
        except Exception as exc:
            raise STTError(f"STT inference failed: {exc}") from exc
