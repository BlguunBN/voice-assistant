"""Local Mongolian Moonshine STT engine."""

from __future__ import annotations

import gc
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from src.core.config import AppConfig
from .engine import STTError
from .mn_tokenizer import MnBPETokenizer

LOGGER = logging.getLogger(__name__)


class MoonshineSTTEngine:
    """Run the Apache-2.0 Moonshine Mongolian checkpoint from local files."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.device = "cpu"
        self.loaded = False
        self.last_detected_language: str | None = None
        self.last_latency_seconds: float | None = None
        self._feature_extractor: Any = None
        self._model: Any = None
        self._tokenizer: MnBPETokenizer | None = None
        self._forced_device: str | None = None

    @property
    def model_id(self) -> str:
        return self.config.stt_mongolian_model_id

    @property
    def model_path(self) -> Path:
        return self.config.stt_mongolian_local_path

    def _choose_device(self) -> str:
        requested = self._forced_device or self.config.stt_device
        if requested == "cpu":
            return "cpu"
        if requested == "cuda":
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if self.config.stt_fallback_device == "cpu":
                return "cpu"
        raise STTError("CUDA is unavailable and no usable STT CPU fallback is configured")

    def load(self) -> None:
        if self.loaded:
            return
        if not self.model_path.is_dir():
            raise STTError(f"Mongolian STT model is not installed at {self.model_path}. Run scripts/download_stt.py --language mn.")
        try:
            import torch
            from transformers import AutoFeatureExtractor, MoonshineForConditionalGeneration

            self.device = self._choose_device()
            self._feature_extractor = AutoFeatureExtractor.from_pretrained(str(self.model_path), local_files_only=True)
            self._tokenizer = MnBPETokenizer(vocab_file=str(self.model_path / "mn_bpe.model"))
            self._model = MoonshineForConditionalGeneration.from_pretrained(str(self.model_path), local_files_only=True)
            self._model.to(self.device).eval()
            self.loaded = True
        except Exception as exc:
            if self.device == "cuda" and "out of memory" in str(exc).lower():
                LOGGER.warning("CUDA OOM while loading Moonshine; retrying on CPU")
                self.unload()
                self._forced_device = "cpu"
                self.load()
                return
            self.unload()
            raise STTError(f"Unable to load Mongolian STT model: {exc}") from exc

    def unload(self) -> None:
        self._feature_extractor = self._model = self._tokenizer = None
        self.loaded = False
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def transcribe(self, audio: str | Path, *, language: str = "mn") -> str:
        if language not in {"mn", "auto"}:
            raise STTError("Moonshine only supports Mongolian; route English requests to Qwen ASR")
        self.load()
        path = Path(audio)
        if not path.is_file():
            raise STTError(f"Audio file not found: {path}")
        try:
            samples, rate = sf.read(path, dtype="float32", always_2d=False)
            waveform = np.asarray(samples, dtype=np.float32)
            if waveform.ndim == 2:
                waveform = waveform.mean(axis=1)
            if waveform.ndim != 1 or waveform.size == 0:
                raise STTError("Audio must contain a non-empty waveform")
            if rate != self.config.stt_sample_rate:
                waveform = np.interp(
                    np.linspace(0, waveform.size - 1, max(1, round(waveform.size * self.config.stt_sample_rate / rate))),
                    np.arange(waveform.size), waveform,
                ).astype(np.float32)
            rms = float(np.sqrt(np.mean(np.square(waveform))))
            if rms > 1e-8:
                waveform = waveform * (0.075 / rms)
            import torch

            inputs = self._feature_extractor(waveform, sampling_rate=self.config.stt_sample_rate, return_tensors="pt")
            started = time.perf_counter()
            with torch.inference_mode():
                generated_ids = self._model.generate(
                    inputs.input_values.to(self.device),
                    max_new_tokens=min(self.config.stt_max_new_tokens, max(5, min(int(waveform.size / self.config.stt_sample_rate * 8), 120))),
                )
            self.last_latency_seconds = time.perf_counter() - started
            result = self._tokenizer.decode_ids(generated_ids[0].tolist()).strip() if self._tokenizer else ""
            if not result:
                raise STTError("Mongolian STT returned empty text")
            self.last_detected_language = "mn"
            return result
        except STTError:
            raise
        except Exception as exc:
            raise STTError(f"Mongolian STT inference failed: {exc}") from exc
