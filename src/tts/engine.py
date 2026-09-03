from __future__ import annotations

import gc
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any

import soundfile as sf

from src.core.config import AppConfig


LOGGER = logging.getLogger(__name__)


class TTSError(RuntimeError):
    """Raised when loading or synthesizing Mongolian speech fails."""


class TTSEngine:
    """Local Coqui TTS wrapper for the downloaded Mongolian VITS checkpoint."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.device = "cpu"
        self.loaded = False
        self.load_time_seconds: float | None = None
        self.last_synthesis_seconds: float | None = None
        self.last_audio_duration_seconds: float | None = None
        self._tts: Any = None
        self._speakers: dict[str, int] = {}

    @property
    def model_path(self) -> Path:
        return self.config.tts_local_path

    @property
    def voices_path(self) -> Path:
        return self.model_path / "speakers.pth"
    @property
    def runtime_config_path(self) -> Path:
        """Return a local config with the upstream Linux speaker path corrected."""
        runtime_path = self.model_path / "config.local.json"
        payload = json.loads((self.model_path / "config.json").read_text(encoding="utf-8"))
        speaker_path = str(self.voices_path)
        if isinstance(payload.get("model_args"), dict):
            payload["model_args"]["speakers_file"] = speaker_path
        payload["speakers_file"] = speaker_path
        runtime_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return runtime_path

    def load(self) -> None:
        """Load the VITS model and actual speaker mapping exactly once."""
        if self.loaded:
            return
        if self.config.tts_device != "cpu":
            raise TTSError("Stage 2 TTS is CPU-only; set tts.device to cpu")
        required = (
            self.model_path / "best_model.pth",
            self.model_path / "config.json",
            self.voices_path,
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise TTSError(f"TTS model files are missing: {', '.join(missing)}")

        started = time.perf_counter()
        try:
            import torch
            from TTS.api import TTS

            speakers = torch.load(self.voices_path, map_location="cpu", weights_only=False)
            if not isinstance(speakers, dict) or not speakers:
                raise TTSError("TTS speaker mapping is empty or has an invalid format")
            self._speakers = {str(name): int(index) for name, index in speakers.items()}
            self._tts = TTS(
                model_path=str(self.model_path / "best_model.pth"),
                config_path=str(self.runtime_config_path),
                speakers_file_path=str(self.voices_path),
                progress_bar=False,
                gpu=False,
            )
            self.loaded = True
            self.load_time_seconds = time.perf_counter() - started
            LOGGER.info(
                "Loaded TTS model=%s device=cpu speakers=%d load_seconds=%.3f",
                self.config.tts_model_id,
                len(self._speakers),
                self.load_time_seconds,
            )
        except TTSError:
            raise
        except Exception as exc:
            self.unload()
            raise TTSError(f"Unable to load TTS model: {exc}") from exc

    def unload(self) -> None:
        """Release TTS model resources."""
        self._tts = None
        self._speakers = {}
        self.loaded = False
        gc.collect()

    def voices(self) -> list[str]:
        """Return speaker identifiers discovered from speakers.pth."""
        self.load()
        return [name for name, _ in sorted(self._speakers.items(), key=lambda item: item[1])]

    def _speaker(self, speaker_id: str | None) -> str:
        selected = speaker_id or self.config.tts_speaker_id
        if selected is None:
            selected = self.voices()[0]
        if selected not in self._speakers:
            available = ", ".join(self.voices())
            raise TTSError(f"Unknown speaker {selected!r}; available speakers: {available}")
        return selected

    def synthesize(self, text: str, speaker_id: str | None = None, output_path: str | Path | None = None) -> Path:
        """Generate a playable WAV file on CPU and return its path."""
        self.load()
        if not text or not text.strip():
            raise TTSError("TTS text must not be empty")
        speaker = self._speaker(speaker_id)
        if output_path is None:
            self.config.project_root.joinpath("cache").mkdir(parents=True, exist_ok=True)
            handle, generated_path = tempfile.mkstemp(
                suffix=".wav",
                prefix="tts-",
                dir=self.config.project_root / "cache",
            )
            os.close(handle)
            Path(generated_path).unlink(missing_ok=True)
            output = Path(generated_path)
        else:
            output = Path(output_path).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)

        started = time.perf_counter()
        try:
            written = self._tts.tts_to_file(
                text=text.strip(),
                speaker=speaker,
                file_path=str(output),
                split_sentences=True,
            )
            result = Path(written) if written else output
            if not result.is_file():
                raise TTSError(f"TTS did not create an output WAV: {result}")
            info = sf.info(result)
            if info.frames <= 0 or info.samplerate <= 0:
                raise TTSError(f"TTS output is not a valid non-empty audio file: {result}")
            self.last_synthesis_seconds = time.perf_counter() - started
            self.last_audio_duration_seconds = info.frames / info.samplerate
            LOGGER.info(
                "TTS synthesis_seconds=%.3f audio_seconds=%.3f speaker=%s output=%s",
                self.last_synthesis_seconds,
                self.last_audio_duration_seconds,
                speaker,
                result,
            )
            return result
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"TTS synthesis failed: {exc}") from exc

    def speak(self, text: str, speaker_id: str | None = None, output_path: str | Path | None = None) -> Path:
        """Synthesize, play through the Windows default device, and retain explicit outputs."""
        output = self.synthesize(text, speaker_id=speaker_id, output_path=output_path)
        temporary = output_path is None
        try:
            import winsound

            winsound.PlaySound(str(output), winsound.SND_FILENAME)
        except ImportError as exc:
            raise TTSError("Windows audio playback is unavailable on this platform") from exc
        except Exception as exc:
            raise TTSError(f"Windows audio playback failed: {exc}") from exc
        finally:
            if temporary:
                output.unlink(missing_ok=True)
        return output
