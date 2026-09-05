from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.core.config import load_config


def _targets(config, _language: str) -> list[tuple[str, Path]]:
    """Every language option maps to the one multilingual Whisper download."""
    return [(config.stt_model_id, config.stt_local_path)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local Whisper STT models")
    parser.add_argument(
        "--language",
        choices=("mn", "en", "auto", "all"),
        default="mn",
        help="Compatibility option; every choice downloads the shared multilingual model",
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
            allow_patterns=["*.json", "*.txt", "*.safetensors", "*.bin", ".gitattributes"],
            max_workers=4,
        )
        print(location)


if __name__ == "__main__":
    main()
