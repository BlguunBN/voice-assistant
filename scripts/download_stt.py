from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.core.config import load_config


def _targets(config, language: str) -> list[tuple[str, Path]]:
    if language == "mn":
        return [(config.stt_model_id, config.stt_local_path)]
    if language == "en":
        return [(config.stt_english_model_id, config.stt_english_local_path)]
    if language == "auto":
        return [(config.stt_auto_model_id, config.stt_auto_local_path)]
    return [
        (config.stt_model_id, config.stt_local_path),
        (config.stt_english_model_id, config.stt_english_local_path),
        (config.stt_auto_model_id, config.stt_auto_local_path),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local Whisper STT models")
    parser.add_argument(
        "--language",
        choices=("mn", "en", "auto", "all"),
        default="mn",
        help="Model to download (default: mn)",
    )
    args = parser.parse_args()
    config = load_config(ROOT / "config" / "config.yaml")
    config.huggingface_cache.mkdir(parents=True, exist_ok=True)
    for model_id, model_path in _targets(config, args.language):
        model_path.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {model_id} into {model_path}")
        location = snapshot_download(
            repo_id=model_id,
            local_dir=str(model_path),
            cache_dir=str(config.huggingface_cache),
            allow_patterns=["*.json", "*.txt", "*.safetensors", ".gitattributes"],
            max_workers=4,
        )
        print(location)


if __name__ == "__main__":
    main()
