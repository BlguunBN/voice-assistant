from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


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
    def stt_english_model_id(self) -> str:
        return str(self.data["stt"].get("english_model", "openai/whisper-small.en"))

    @property
    def stt_english_local_path(self) -> Path:
        value = self.data["stt"].get("english_local_path")
        if value is None:
            return self.stt_local_path.parent / "whisper-small.en"
        return self._path("stt", "english_local_path")
    @property
    def stt_auto_model_id(self) -> str:
        return str(self.data["stt"].get("auto_model", "openai/whisper-tiny"))

    @property
    def stt_auto_local_path(self) -> Path:
        value = self.data["stt"].get("auto_local_path")
        if value is None:
            return self.stt_local_path.parent / "whisper-tiny-auto"
        return self._path("stt", "auto_local_path")

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
    def tts_provider(self) -> str:
        return str(self.data["tts"].get("provider", "local")).strip().lower()

    @property
    def tts_edge_voice(self) -> str:
        return str(self.data["tts"].get("edge_voice", "mn-MN-YesuiNeural")).strip()

    @property
    def tts_edge_rate(self) -> str:
        return str(self.data["tts"].get("edge_rate", "+0%")).strip()

    @property
    def tts_edge_volume(self) -> str:
        return str(self.data["tts"].get("edge_volume", "+0%")).strip()

    @property
    def tts_edge_pitch(self) -> str:
        return str(self.data["tts"].get("edge_pitch", "+0Hz")).strip()

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
    def tts_english_model(self) -> str:
        section = self.data.get("tts", {})
        value = section.get("english_model") if isinstance(section, dict) else None
        return str(value or "hexgrad/Kokoro-82M")

    @property
    def tts_english_voice(self) -> str:
        section = self.data.get("tts", {})
        value = section.get("english_voice") if isinstance(section, dict) else None
        return str(value or "af_heart")

    @property
    def tts_english_device(self) -> str:
        section = self.data.get("tts", {})
        value = section.get("english_device") if isinstance(section, dict) else None
        return str(value or "cpu").lower()

    @property
    def llm_provider(self) -> str:
        section = self.data.get("llm", {})
        value = section.get("provider") if isinstance(section, dict) else None
        return str(value or "echo").strip().lower()

    @property
    def llm_base_url(self) -> str:
        section = self.data.get("llm", {})
        value = section.get("base_url") if isinstance(section, dict) else None
        return os.getenv("NVIDIA_NIM_BASE_URL", str(value or "https://integrate.api.nvidia.com/v1")).strip().rstrip("/")

    @property
    def llm_model(self) -> str:
        section = self.data.get("llm", {})
        configured = section.get("model") if isinstance(section, dict) else None
        return os.getenv("NVIDIA_NIM_MODEL", str(configured or "")).strip()

    @property
    def llm_api_key_env(self) -> str:
        section = self.data.get("llm", {})
        value = section.get("api_key_env") if isinstance(section, dict) else None
        return str(value or "NVIDIA_API_KEY").strip()

    @property
    def llm_timeout_seconds(self) -> float:
        section = self.data.get("llm", {})
        value = section.get("timeout_seconds") if isinstance(section, dict) else None
        return float(value if value is not None else 60.0)

    @property
    def llm_temperature(self) -> float:
        section = self.data.get("llm", {})
        value = section.get("temperature") if isinstance(section, dict) else None
        return float(value if value is not None else 0.2)

    @property
    def llm_max_tokens(self) -> int:
        section = self.data.get("llm", {})
        value = section.get("max_tokens") if isinstance(section, dict) else None
        return int(value if value is not None else 512)

    @property
    def llm_system_prompt(self) -> str:
        section = self.data.get("llm", {})
        value = section.get("system_prompt") if isinstance(section, dict) else None
        return str(value or "You are a helpful local voice assistant. Reply concisely in the same language as the user, Mongolian or English.")

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

    @property
    def desktop_hotkey(self) -> str:
        section = self.data.get("desktop", {})
        value = section.get("hotkey") if isinstance(section, dict) else None
        return str(value or "ctrl+shift+space").strip().lower()

    @property
    def desktop_language(self) -> str:
        section = self.data.get("desktop", {})
        value = section.get("language") if isinstance(section, dict) else None
        return str(value or "mn").strip().lower()

    @property
    def vad_enabled(self) -> bool:
        return bool(self.data["vad"]["enabled"])

    @property
    def vad_start_threshold(self) -> float:
        return float(self.data["vad"]["start_threshold"])

    @property
    def vad_stop_threshold(self) -> float:
        return float(self.data["vad"]["stop_threshold"])

    @property
    def vad_silence_seconds(self) -> float:
        return float(self.data["vad"]["silence_seconds"])

    @property
    def vad_min_speech_seconds(self) -> float:
        return float(self.data["vad"]["min_speech_seconds"])
    @property
    def api_host(self) -> str:
        return str(self.data["api"]["host"]).strip()

    @property
    def api_port(self) -> int:
        return int(self.data["api"]["port"])

    @property
    def api_max_upload_bytes(self) -> int:
        return int(self.data["api"]["max_upload_bytes"])
    @property
    def logging_enabled(self) -> bool:
        return bool(self.data["logging"]["enabled"])

    @property
    def save_recordings(self) -> bool:
        return bool(self.data["logging"]["save_recordings"])
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
        expanded = Path(os.path.expandvars(os.path.expanduser(value)))
        if expanded.is_absolute():
            return expanded.resolve()

        storage = self.data.get("storage", {})
        root_value = storage.get("root", ".") if isinstance(storage, dict) else "."
        if not isinstance(root_value, str) or not root_value.strip():
            raise ConfigError("storage.root must be a non-empty path")
        configured_root = Path(os.path.expandvars(os.path.expanduser(root_value)))
        base_root_value = os.getenv("VOICE_ASSISTANT_ROOT")
        base_root = (
            Path(os.path.expandvars(os.path.expanduser(base_root_value)))
            if base_root_value and base_root_value.strip()
            else self.path.parent.parent
        )
        if not configured_root.is_absolute():
            configured_root = base_root / configured_root
        return (configured_root / expanded).resolve()

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
        if not self.stt_model_id.strip():
            raise ConfigError("stt.model must be non-empty")
        if not self.stt_english_model_id.strip():
            raise ConfigError("stt.english_model must be non-empty")
        if not self.tts_model_id.strip():
            raise ConfigError("tts.model must be non-empty")
        if self.tts_provider not in {"local", "edge"}:
            raise ConfigError("tts.provider must be either 'local' or 'edge'")
        if not self.tts_edge_voice:
            raise ConfigError("tts.edge_voice must be non-empty")
        if self.tts_device != "cpu":
            raise ConfigError("tts.device must be 'cpu' for Stage 2")
        if not self.tts_english_model.strip():
            raise ConfigError("tts.english_model must be non-empty")
        if not self.tts_english_voice.strip():
            raise ConfigError("tts.english_voice must be non-empty")
        if self.tts_english_device not in {"cpu", "cuda"}:
            raise ConfigError("tts.english_device must be either 'cpu' or 'cuda'")
        if self.llm_provider not in {"echo", "nvidia_nim"}:
            raise ConfigError("llm.provider must be 'echo' or 'nvidia_nim'")
        if self.llm_provider == "nvidia_nim" and not self.llm_base_url.startswith("https://"):
            raise ConfigError("llm.base_url must use HTTPS for hosted NVIDIA NIM")
        if self.llm_timeout_seconds <= 0:
            raise ConfigError("llm.timeout_seconds must be positive")
        if not 0 <= self.llm_temperature <= 2:
            raise ConfigError("llm.temperature must be between 0 and 2")
        if self.llm_max_tokens < 1:
            raise ConfigError("llm.max_tokens must be positive")
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
        if self.vad_start_threshold <= 0 or self.vad_stop_threshold <= 0:
            raise ConfigError("vad thresholds must be positive")
        if self.vad_stop_threshold > self.vad_start_threshold:
            raise ConfigError("vad.stop_threshold must not exceed vad.start_threshold")
        if self.vad_silence_seconds <= 0:
            raise ConfigError("vad.silence_seconds must be positive")
        if self.vad_min_speech_seconds <= 0:
            raise ConfigError("vad.min_speech_seconds must be positive")
        from src.audio.hotkey import HotkeyError, KeyChord

        try:
            KeyChord.parse(self.desktop_hotkey)
        except HotkeyError as exc:
            raise ConfigError(str(exc)) from exc
        if self.desktop_language not in {"mn", "en", "auto"}:
            raise ConfigError("desktop.language must be 'mn', 'en', or 'auto'")
        if self.api_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigError("api.host must bind to localhost only")
        if not 1 <= self.api_port <= 65_535:
            raise ConfigError("api.port must be between 1 and 65535")
        if self.api_max_upload_bytes < 1:
            raise ConfigError("api.max_upload_bytes must be positive")
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
    load_dotenv(config_path.parent.parent / ".env")
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
    os.environ.setdefault("HF_HOME", str(config.huggingface_home))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(config.huggingface_cache))
    return config
