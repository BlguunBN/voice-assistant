from __future__ import annotations

import gc
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np
import soundfile as sf

from src.core.config import AppConfig
from src.tts.engine import TTSError


LOGGER = logging.getLogger(__name__)


class EnglishTTSEngine:
    """Lazy-loaded Kokoro English TTS backend with a stock female voice."""

    sample_rate = 24_000

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.requested_device = config.tts_english_device
        self.device = self.requested_device
        self.loaded = False
        self.load_time_seconds: float | None = None
        self.last_synthesis_seconds: float | None = None
        self.last_audio_duration_seconds: float | None = None
        self._pipeline: Any = None

    def _resolve_device(self) -> str:
        if self.requested_device != "cuda":
            return self.requested_device
        try:
            import torch
        except Exception as exc:
            LOGGER.warning("CUDA unavailable for English TTS (%s); falling back to CPU", exc)
            return "cpu"
        if not torch.cuda.is_available():
            LOGGER.warning("CUDA unavailable for English TTS; falling back to CPU")
            return "cpu"
        return "cuda"

    def load(self) -> None:
        if self.loaded:
            return
        self.device = self._resolve_device()
        started = time.perf_counter()
        try:
            from kokoro import KPipeline

            self._pipeline = KPipeline(
                lang_code="a",
                repo_id=self.config.tts_english_model,
                device=self.device,
            )
            self.loaded = True
            self.load_time_seconds = time.perf_counter() - started
            LOGGER.info(
                "Loaded English TTS model=%s voice=%s device=%s load_seconds=%.3f",
                self.config.tts_english_model,
                self.config.tts_english_voice,
                self.device,
                self.load_time_seconds,
            )
        except Exception as exc:
            self.unload()
            raise TTSError(f"Unable to load English TTS model: {exc}") from exc

    def unload(self) -> None:
        self._pipeline = None
        self.loaded = False
        gc.collect()

    def _voice(self, speaker_id: str | None) -> str:
        selected = speaker_id or self.config.tts_english_voice
        if selected != self.config.tts_english_voice:
            raise TTSError(f"Unknown English voice: {selected}")
        return selected

    def voices(self) -> list[str]:
        self.load()
        return [self.config.tts_english_voice]

    def synthesize(
        self,
        text: str,
        speaker_id: str | None = None,
        output_path: str | Path | None = None,
    ) -> Path:
        self.load()
        if not text or not text.strip():
            raise TTSError("English TTS text must not be empty")
        if output_path is None:
            raise TTSError("English TTS requires an explicit output path")
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        try:
            chunks: list[np.ndarray] = []
            for _, _, audio in self._pipeline(
                text.strip(),
                voice=self._voice(speaker_id),
                speed=1.0,
                split_pattern=r"\n+",
            ):
                if hasattr(audio, "detach"):
                    audio = audio.detach().cpu().numpy()
                chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
                if chunk.size:
                    chunks.append(chunk)
            if not chunks:
                raise TTSError("English TTS produced no audio")
            sf.write(output, np.concatenate(chunks), self.sample_rate)
            if not output.is_file():
                raise TTSError(f"English TTS did not create an output WAV: {output}")
            info = sf.info(output)
            if info.frames <= 0 or info.samplerate <= 0:
                raise TTSError(f"English TTS output is not a valid non-empty audio file: {output}")
            self.last_synthesis_seconds = time.perf_counter() - started
            self.last_audio_duration_seconds = info.frames / info.samplerate
            return output
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"English TTS synthesis failed: {exc}") from exc
