from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from src.core.config import AppConfig, ConfigError, load_config
from src.stt.engine import STTError, STTEngine


LOGGER = logging.getLogger(__name__)


def configure_logging(config: AppConfig) -> None:
    log_path = config.project_root / "logs" / "voice-assistant.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )


def _torch_status() -> tuple[str, str, int | None]:
    try:
        import torch
    except ImportError:
        return "not installed", "unavailable", None
    available = bool(torch.cuda.is_available())
    if not available:
        return torch.__version__, "unavailable", None
    properties = torch.cuda.get_device_properties(0)
    return torch.__version__, torch.cuda.get_device_name(0), int(properties.total_memory)


def print_status(config: AppConfig) -> None:
    torch_version, gpu_name, vram = _torch_status()
    model_path = config.stt_local_path
    print("STT model")
    print(f"  repository: {config.stt_model_id}")
    print(f"  path: {model_path}")
    print(f"  installation status: {'installed' if model_path.is_dir() else 'missing'}")
    print("  load status: not loaded (start a transcription to load once)")
    print(f"  configured device: {config.stt_device}")
    print(f"  fallback device: {config.stt_fallback_device}")
    print("PyTorch")
    print(f"  version: {torch_version}")
    print(f"  CUDA/GPU: {gpu_name}")
    if vram is not None:
        print(f"  VRAM: {vram / (1024**3):.2f} GiB")
    print(f"Hugging Face cache: {config.huggingface_cache}")


def transcribe(config: AppConfig, audio_path: str) -> int:
    engine = STTEngine(config)
    result = engine.transcribe(Path(audio_path))
    print(result)
    if engine.last_latency_seconds is not None:
        LOGGER.info(
            "CLI transcription completed path=%s latency_seconds=%.3f device=%s",
            audio_path,
            engine.last_latency_seconds,
            engine.device,
        )
    engine.unload()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Mongolian voice assistant")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config YAML (defaults to config/config.yaml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show local STT and hardware status")
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe a WAV/audio file")
    transcribe_parser.add_argument("audio", help="Path to the audio file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        configure_logging(config)
        if args.command == "status":
            print_status(config)
            return 0
        if args.command == "transcribe":
            return transcribe(config, args.audio)
        raise ConfigError(f"Unsupported command: {args.command}")
    except (ConfigError, STTError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
