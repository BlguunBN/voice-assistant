from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from src.core.config import load_config
from src.tts.english import EnglishTTSEngine


def test_english_tts_uses_kokoro_female_voice_and_writes_24khz_wav(monkeypatch, tmp_path: Path):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    captured: dict[str, object] = {}

    class FakePipeline:
        def __init__(self, *, lang_code, repo_id, device):
            captured["init"] = {"lang_code": lang_code, "repo_id": repo_id, "device": device}

        def __call__(self, text, *, voice, speed, split_pattern):
            captured["call"] = {
                "text": text,
                "voice": voice,
                "speed": speed,
                "split_pattern": split_pattern,
            }
            yield (text, "phonemes", np.ones(2_400, dtype=np.float32))

    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=FakePipeline))
    engine = EnglishTTSEngine(load_config())
    output = tmp_path / "english.wav"

    result = engine.synthesize("Hello there.", output_path=output)

    assert result == output
    assert captured["init"] == {
        "lang_code": "a",
        "repo_id": "hexgrad/Kokoro-82M",
        "device": "cuda",
    }
    assert captured["call"] == {
        "text": "Hello there.",
        "voice": "af_heart",
        "speed": 1.0,
        "split_pattern": r"\n+",
    }
    info = sf.info(result)
    assert info.samplerate == 24_000
    assert info.frames == 2_400
    assert engine.loaded is True
    assert engine.last_audio_duration_seconds == 0.1


def test_english_tts_rejects_unknown_voice(monkeypatch):
    class FakePipeline:
        def __init__(self, *, lang_code, repo_id, device):
            pass

    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=FakePipeline))
    engine = EnglishTTSEngine(load_config())
    engine.load()

    try:
        try:
            engine._voice("unknown")
        except Exception as exc:
            assert "Unknown English voice" in str(exc)
        else:
            raise AssertionError("unknown voice was accepted")
    finally:
        engine.unload()


def test_english_tts_falls_back_to_cpu_when_cuda_is_unavailable(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    captured: dict[str, str] = {}

    class FakePipeline:
        def __init__(self, *, lang_code, repo_id, device):
            captured["device"] = device

    monkeypatch.setitem(sys.modules, "kokoro", SimpleNamespace(KPipeline=FakePipeline))
    engine = EnglishTTSEngine(load_config())
    engine.load()

    try:
        assert engine.device == "cpu"
        assert captured["device"] == "cpu"
    finally:
        engine.unload()
