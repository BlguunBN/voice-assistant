from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.core.config import load_config


if __name__ == "__main__":
    config = load_config(ROOT / "config" / "config.yaml")
    config.tts_local_path.parent.mkdir(parents=True, exist_ok=True)
    config.huggingface_cache.mkdir(parents=True, exist_ok=True)
    location = snapshot_download(
        repo_id=config.tts_model_id,
        local_dir=str(config.tts_local_path),
        cache_dir=str(config.huggingface_cache),
        allow_patterns=["best_model.pth", "config.json", "speakers.pth", ".gitattributes"],
        max_workers=4,
    )
    print(location)
