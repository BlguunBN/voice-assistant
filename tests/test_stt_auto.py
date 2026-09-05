from __future__ import annotations

import numpy as np
import pytest
import torch

from src.core.config import load_config
from src.stt.engine import STTEngine, STTError


class AutoProcessor:
    class tokenizer:
        @staticmethod
        def convert_ids_to_tokens(token_id: int) -> str:
            return {41: "<|mn|>", 42: "<|en|>", 99: "<|fr|>"}.get(token_id, "<|startoftranscript|>")

    def __call__(self, *_args, **_kwargs):
        return {"input_features": torch.zeros((1, 80, 8))}

    def batch_decode(self, _ids, *, skip_special_tokens):
        assert skip_special_tokens
        return ["test transcript"]


class AutoModel:
    dtype = torch.float32

    def __init__(self, token_id: int) -> None:
        self.token_id = token_id
        self.kwargs: dict[str, object] = {}

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return torch.tensor([[1, self.token_id, 3]])


@pytest.mark.parametrize("token_id, expected", [(41, "mn"), (42, "en")])
def test_auto_detection_uses_language_token_from_single_generation(token_id: int, expected: str):
    engine = STTEngine(load_config(), language="auto")
    engine._processor, engine._model, engine.loaded = AutoProcessor(), AutoModel(token_id), True
    assert engine.transcribe(np.zeros(16_000, dtype=np.float32), language="auto") == "test transcript"
    assert engine.last_detected_language == expected
    assert "language" not in engine._model.kwargs


def test_auto_rejects_unsupported_detected_language():
    engine = STTEngine(load_config(), language="auto")
    engine._processor, engine._model, engine.loaded = AutoProcessor(), AutoModel(99), True
    with pytest.raises(STTError, match="unsupported language"):
        engine.transcribe(np.zeros(16_000, dtype=np.float32), language="auto")


def test_desktop_language_defaults_to_auto():
    assert load_config().desktop_language == "auto"


def test_cuda_oom_unloads_gpu_model_and_retries_once_on_cpu(monkeypatch: pytest.MonkeyPatch):
    engine = STTEngine(load_config())
    engine.loaded, engine.device = True, "cuda"
    calls: list[str] = []

    def fake_loaded(_audio, _language):
        calls.append(engine.device)
        if engine.device == "cuda":
            raise RuntimeError("CUDA out of memory")
        engine.last_detected_language = "en"
        return "Hello"

    monkeypatch.setattr(engine, "_read_audio", lambda _audio: np.zeros(16_000, dtype=np.float32))
    monkeypatch.setattr(engine, "_transcribe_loaded", fake_loaded)
    monkeypatch.setattr(engine, "unload", lambda: setattr(engine, "loaded", False))

    def fake_load():
        if not engine.loaded:
            engine.loaded, engine.device = True, "cpu"

    monkeypatch.setattr(engine, "load", fake_load)
    assert engine.transcribe(np.zeros(16_000, dtype=np.float32), language="en") == "Hello"
    assert calls == ["cuda", "cpu"]


def test_cuda_unavailable_uses_cpu_fallback(monkeypatch: pytest.MonkeyPatch):
    engine = STTEngine(load_config())
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert engine._choose_device() == "cpu"
