from __future__ import annotations

import gc
import logging
import os
from pathlib import Path
import time
from typing import Any, Literal, Mapping

import numpy as np
import soundfile as sf

from src.core.config import AppConfig

LOGGER = logging.getLogger(__name__)
STTLanguage = Literal["mn", "en", "auto"]
_SUPPORTED_LANGUAGES = frozenset({"mn", "en"})


class STTError(RuntimeError):
    """Raised when loading or running the speech-to-text engine fails."""


class STTEngine:
    """One resident multilingual Whisper model with CUDA-to-CPU recovery."""

    def __init__(self, config: AppConfig, *, language: STTLanguage = "mn") -> None:
        self.config, self.language, self.device, self.loaded = config, language, "cpu", False
        self.load_time_seconds: float | None = None
        self.last_latency_seconds: float | None = None
        self.last_audio_duration_seconds: float | None = None
        self.last_real_time_factor: float | None = None
        self.last_peak_vram_bytes: int | None = None
        self.last_detected_language: str | None = None
        self._processor: Any = None
        self._model: Any = None
        self._forced_device: str | None = None

    @property
    def model_id(self) -> str:
        return self.config.stt_model_id

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
            if self.config.stt_fallback_device == "cpu":
                LOGGER.warning("CUDA is unavailable; using configured CPU fallback")
                return "cpu"
            raise STTError("CUDA is unavailable and no usable fallback device is configured")
        raise STTError(f"Unsupported STT device: {requested}")

    def load(self) -> None:
        """Load the single model once and retain it across requests."""
        if self.loaded:
            return
        if not self.model_path.is_dir():
            raise STTError(f"STT model is not installed at {self.model_path}. Download {self.model_id} into that directory first.")
        started = time.perf_counter()
        try:
            import torch
            from transformers import AutoProcessor, WhisperForConditionalGeneration
            self.device = self._choose_device()
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            self._processor = AutoProcessor.from_pretrained(str(self.model_path), local_files_only=True, extra_special_tokens={})
            self._model = WhisperForConditionalGeneration.from_pretrained(
                str(self.model_path), local_files_only=True, dtype=dtype
            )
            self._model.to(self.device)
            self._model.eval()
            self.loaded = True
            self.load_time_seconds = time.perf_counter() - started
            LOGGER.info("Loaded STT model=%s device=%s load_seconds=%.3f", self.model_id, self.device, self.load_time_seconds)
        except STTError:
            raise
        except Exception as exc:
            self.unload()
            raise STTError(f"Unable to load STT model: {exc}") from exc

    def unload(self) -> None:
        self._processor = self._model = None
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
        return np.interp(np.linspace(0, audio.size - 1, max(1, round(audio.size * target_rate / source_rate))), np.linspace(0, audio.size - 1, audio.size), audio).astype(np.float32)

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
        else:
            array, sample_rate = np.asarray(audio, dtype=np.float32), self.config.stt_sample_rate
        if array.ndim == 2:
            array = array.mean(axis=1)
        if array.ndim != 1 or array.size == 0:
            raise STTError("Audio must contain a non-empty mono or multi-channel waveform")
        if not np.isfinite(array).all():
            raise STTError("Audio contains NaN or infinite samples")
        return self._resample(array, int(sample_rate), self.config.stt_sample_rate)

    @staticmethod
    def _move_inputs(inputs: Mapping[str, Any], device: str, dtype: Any = None) -> dict[str, Any]:
        return {key: value.to(device=device, dtype=dtype) if hasattr(value, "to") and dtype is not None and getattr(value, "is_floating_point", lambda: False)() else value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}

    def _detected_language_from_ids(self, generated_ids: Any) -> str | None:
        converter = getattr(getattr(self._processor, "tokenizer", None), "convert_ids_to_tokens", None)
        if converter is None:
            return None
        for token_id in generated_ids[0].tolist():
            token = str(converter(int(token_id))).strip("<|>").lower()
            if token in _SUPPORTED_LANGUAGES:
                return token
        return None

    def _transcribe_loaded(self, audio: np.ndarray, language: STTLanguage) -> str:
        import torch
        inputs = self._processor(audio, sampling_rate=self.config.stt_sample_rate, return_tensors="pt", return_attention_mask=True)
        model_inputs = self._move_inputs(inputs, self.device, getattr(self._model, "dtype", None))
        if self.device == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        kwargs: dict[str, Any] = {"max_new_tokens": self.config.stt_max_new_tokens, "task": "transcribe"}
        if language in _SUPPORTED_LANGUAGES:
            kwargs["language"] = language
        with torch.inference_mode():
            generated_ids = self._model.generate(**model_inputs, **kwargs)
        if self.device == "cuda":
            torch.cuda.synchronize()
        self.last_latency_seconds = time.perf_counter() - started
        self.last_real_time_factor = self.last_latency_seconds / self.last_audio_duration_seconds if self.last_audio_duration_seconds else None
        self.last_peak_vram_bytes = int(torch.cuda.max_memory_allocated()) if self.device == "cuda" else None
        detected = language if language in _SUPPORTED_LANGUAGES else self._detected_language_from_ids(generated_ids)
        if language == "auto" and detected not in _SUPPORTED_LANGUAGES:
            raise STTError("Whisper detected an unsupported language; only Mongolian and English are accepted")
        self.last_detected_language = detected
        result = str(self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]).strip()
        if not result:
            raise STTError("STT returned empty text")
        LOGGER.info("STT latency_seconds=%.3f audio_seconds=%.3f rtf=%.3f detected_language=%s", self.last_latency_seconds, self.last_audio_duration_seconds or 0.0, self.last_real_time_factor or 0.0, detected)
        return result

    def transcribe(self, audio: str | os.PathLike[str] | np.ndarray, language: STTLanguage | None = None) -> str:
        requested: STTLanguage = language or self.language
        if requested not in {"mn", "en", "auto"}:
            raise STTError(f"Unsupported STT language: {requested}")
        self.load()
        samples = self._read_audio(audio)
        self.last_audio_duration_seconds = samples.size / self.config.stt_sample_rate
        if self.device == "cuda":
            import torch
            torch.cuda.reset_peak_memory_stats()
        try:
            return self._transcribe_loaded(samples, requested)
        except STTError:
            raise
        except RuntimeError as exc:
            if self.device != "cuda" or "out of memory" not in str(exc).lower():
                raise STTError(f"STT inference failed: {exc}") from exc
            LOGGER.exception("CUDA out of memory during STT; unloading and retrying on CPU")
            self.unload()
            self._forced_device = "cpu"
            self.load()
            return self._transcribe_loaded(samples, requested)
        except Exception as exc:
            raise STTError(f"STT inference failed: {exc}") from exc
