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
    """Typed access to the configuration needed by the Stage 1 STT service."""

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
