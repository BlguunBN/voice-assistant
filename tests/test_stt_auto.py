from __future__ import annotations

import numpy as np
import torch

from src.core.config import load_config
from src.stt.engine import STTEngine


class MongolianProcessor:
    class tokenizer:
        @staticmethod
        def convert_ids_to_tokens(_token_id: int) -> str:
            return "<|mn|>"

    def __call__(self, *_args, **_kwargs):
        return {"input_features": torch.zeros((1, 80, 8))}

    def batch_decode(self, _ids, *, skip_special_tokens):
        assert skip_special_tokens
        return ["Сайн байна уу"]


class MongolianModel:
    dtype = torch.float32

    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def generate(self, **kwargs):
        self.kwargs = kwargs
        return torch.tensor([[1, 2, 3]])


def test_every_legacy_language_request_uses_the_mongolian_model():
    engine = STTEngine(load_config())
    model = MongolianModel()
    engine._processor, engine._model, engine.loaded = MongolianProcessor(), model, True

    assert engine.transcribe(np.zeros(16_000, dtype=np.float32), language="auto") == "Сайн байна уу"
    assert model.kwargs["language"] == "mn"
    assert engine.last_detected_language == "mn"


def test_desktop_language_defaults_to_mongolian():
    assert load_config().desktop_language == "mn"
