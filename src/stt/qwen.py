"""Local Qwen3-ASR engine for English transcription."""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from src.core.config import AppConfig
from .engine import STTError


class QwenSTTEngine:
    """Run Qwen3-ASR locally, using FP16 CUDA with a CPU fallback."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.device = "cpu"
        self.loaded = False
        self.last_detected_language: str | None = None
        self._model: Any = None
        self._processor: Any = None
        self._forced_device: str | None = None

    @property
    def model_id(self) -> str:
        return self.config.stt_english_model_id

    @property
    def model_path(self) -> Path:
        return self.config.stt_english_local_path

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
            raise STTError(f"English STT model is not installed at {self.model_path}. Run scripts/download_stt.py --language en.")
        try:
            import torch
            from transformers import AutoModelForMultimodalLM, AutoProcessor

            self.device = self._choose_device()
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            self._processor = AutoProcessor.from_pretrained(str(self.model_path), local_files_only=True)
            self._model = AutoModelForMultimodalLM.from_pretrained(
                str(self.model_path), local_files_only=True, dtype=dtype
            ).to(self.device).eval()
            self.loaded = True
        except Exception as exc:
            if self.device == "cuda" and "out of memory" in str(exc).lower():
                self.unload()
                self._forced_device = "cpu"
                self.load()
                return
            self.unload()
            raise STTError(f"Unable to load English STT model: {exc}") from exc

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

    def _read_audio(self, path: Path) -> np.ndarray:
        try:
            samples, sample_rate = sf.read(path, dtype="float32", always_2d=False)
        except Exception as exc:
            raise STTError(f"Unable to read audio file {path}: {exc}") from exc
        waveform = np.asarray(samples, dtype=np.float32)
        if waveform.ndim == 2:
            waveform = waveform.mean(axis=1)
        if waveform.ndim != 1 or waveform.size == 0:
            raise STTError("Audio must contain a non-empty waveform")
        if sample_rate == self.config.stt_sample_rate:
            return waveform
        target_length = max(1, round(waveform.size * self.config.stt_sample_rate / sample_rate))
        return np.interp(
            np.linspace(0, waveform.size - 1, target_length),
            np.arange(waveform.size),
            waveform,
        ).astype(np.float32)

    def transcribe(self, audio: str | Path, *, language: str = "en") -> str:
        self.load()
        path = Path(audio)
        if not path.is_file():
            raise STTError(f"Audio file not found: {path}")
        try:
            import torch

            # Passing a filesystem path makes Transformers invoke TorchCodec.
            # Decode with the project's SoundFile dependency instead so Windows
            # users do not need matching TorchCodec and FFmpeg DLLs.
            request: dict[str, object] = {"audio": self._read_audio(path)}
            if language == "en":
                request["language"] = "English"
            elif language != "auto":
                raise STTError(f"Qwen STT cannot transcribe requested language: {language}")
            inputs = self._processor.apply_transcription_request(**request).to(self.device, self._model.dtype)
            with torch.inference_mode():
                output_ids = self._model.generate(**inputs, max_new_tokens=self.config.stt_max_new_tokens)
            generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
            parsed = self._processor.decode(generated_ids, return_format="parsed")[0]
            result = str(parsed.get("transcription", "")).strip()
            if not result:
                raise STTError("English STT returned empty text")
            self.last_detected_language = str(parsed.get("language") or "").lower() or None
            return result
        except STTError:
            raise
        except RuntimeError as exc:
            if self.device == "cuda" and "out of memory" in str(exc).lower():
                self.unload()
                self._forced_device = "cpu"
                return self.transcribe(path, language=language)
            raise STTError(f"English STT inference failed: {exc}") from exc
        except Exception as exc:
            raise STTError(f"English STT inference failed: {exc}") from exc
