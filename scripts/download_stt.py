from __future__ import annotations

from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_ID = "Blgn94/whisper-small-mn-v3"
MODEL_PATH = Path("D:/AI/models/stt/whisper-small-mn-v3")
HF_CACHE = Path("D:/AI/huggingface/hub")


if __name__ == "__main__":
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    HF_CACHE.mkdir(parents=True, exist_ok=True)
    location = snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(MODEL_PATH),
        cache_dir=str(HF_CACHE),
        max_workers=4,
    )
    print(location)
