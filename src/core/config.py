from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the application configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    """Typed access to the local Mongolian voice assistant configuration."""

    path: Path
    data: dict[str, Any]

    @property
    def language(self) -> str:
        return str(self.data["system"]["language"])

    @property
    def project_root(self) -> Path:
        return self._path("storage", "project_root")

    @property
    def model_root(self) -> Path:
        return self._path("storage", "model_root")

    @property
    def recordings_root(self) -> Path:
        return self._path("storage", "recordings")

    @property
    def huggingface_home(self) -> Path:
        return self._path("storage", "huggingface_home")

    @property
    def huggingface_cache(self) -> Path:
        return self._path("storage", "huggingface_cache")

    @property
    def stt_model_id(self) -> str:
        return str(self.data["stt"]["model"])

    @property
    def stt_local_path(self) -> Path:
        return self._path("stt", "local_path")

    @property
    def stt_device(self) -> str:
        return str(self.data["stt"]["device"]).lower()

    @property
    def stt_fallback_device(self) -> str:
        return str(self.data["stt"]["fallback_device"]).lower()

    @property
    def stt_sample_rate(self) -> int:
        return int(self.data["stt"]["sample_rate"])

    @property
    def stt_max_new_tokens(self) -> int:
        return int(self.data["stt"]["max_new_tokens"])

    @property
    def tts_model_id(self) -> str:
        return str(self.data["tts"]["model"])

    @property
    def tts_local_path(self) -> Path:
        return self._path("tts", "local_path")

    @property
    def tts_device(self) -> str:
        return str(self.data["tts"]["device"]).lower()

    @property
    def tts_speaker_id(self) -> str | None:
        value = self.data["tts"].get("speaker_id")
        return str(value) if value is not None else None

    @property
    def audio_input_device(self) -> int | str | None:
        return self._device_value(self.data["audio"].get("input_device"), "audio.input_device")

    @property
    def audio_output_device(self) -> int | str | None:
        return self._device_value(self.data["audio"].get("output_device"), "audio.output_device")

    @property
    def audio_sample_rate(self) -> int:
        return int(self.data["audio"]["sample_rate"])

    @property
    def audio_blocksize(self) -> int:
        return int(self.data["audio"]["blocksize"])

    @property
    def audio_max_seconds(self) -> float:
        return float(self.data["audio"]["max_seconds"])

    @property
    def push_to_talk_hotkey(self) -> str:
        return str(self.data["audio"]["push_to_talk_hotkey"]).lower()

    @staticmethod
    def _device_value(value: Any, name: str) -> int | str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ConfigError(f"{name} must be an integer index, name, or null")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            return value.strip()
        raise ConfigError(f"{name} must be an integer index, name, or null")

    def _path(self, section: str, key: str) -> Path:
        value = self.data[section][key]
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{section}.{key} must be a non-empty path")
        return Path(os.path.expandvars(os.path.expanduser(value))).resolve()

    def validate(self) -> None:
        if self.language != "mn":
            raise ConfigError(f"system.language must be 'mn', got {self.language!r}")
        if self.stt_device not in {"cpu", "cuda"}:
            raise ConfigError("stt.device must be either 'cpu' or 'cuda'")
        if self.stt_fallback_device not in {"cpu", "cuda"}:
            raise ConfigError("stt.fallback_device must be either 'cpu' or 'cuda'")
        if self.stt_sample_rate != 16_000:
            raise ConfigError("stt.sample_rate must be 16000 Hz")
        if self.stt_max_new_tokens < 1:
            raise ConfigError("stt.max_new_tokens must be positive")
        if not self.tts_model_id.strip():
            raise ConfigError("tts.model must be non-empty")
        if self.tts_device != "cpu":
            raise ConfigError("tts.device must be 'cpu' for Stage 2")
        if self.audio_sample_rate != self.stt_sample_rate:
            raise ConfigError("audio.sample_rate must match stt.sample_rate")
        if self.audio_sample_rate != 16_000:
            raise ConfigError("audio.sample_rate must be 16000 Hz")
        if self.audio_blocksize < 1:
            raise ConfigError("audio.blocksize must be positive")
        if self.audio_max_seconds <= 0:
            raise ConfigError("audio.max_seconds must be positive")
        if self.push_to_talk_hotkey != "space":
            raise ConfigError("audio.push_to_talk_hotkey must be 'space' for Stage 3")

    def ensure_runtime_directories(self) -> None:
        for directory in (
            self.project_root,
            self.model_root,
            self.recordings_root,
            self.huggingface_home,
            self.huggingface_cache,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "config.yaml"


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path).expanduser().resolve() if path else default_config_path()
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Configuration root must be a mapping: {config_path}")
    config = AppConfig(path=config_path, data=raw)
    config.validate()
    config.ensure_runtime_directories()
    return config
