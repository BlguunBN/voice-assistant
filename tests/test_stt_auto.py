from __future__ import annotations

import numpy as np
import pytest
import torch

from src.core.config import load_config
from src.stt.engine import STTEngine, STTError


class AutoDetectProcessor:
    class tokenizer:
        @staticmethod
        def convert_ids_to_tokens(token_id: int) -> str:
            return {41: "<|mn|>", 42: "<|en|>"}.get(token_id, "<|fr|>")

    def __call__(self, audio, *, sampling_rate, return_tensors, return_attention_mask):
        assert sampling_rate == 16_000
        assert return_tensors == "pt"
        assert return_attention_mask is True
        return {"input_features": torch.zeros((1, 80, 8))}


class AutoDetectModel:
    def __init__(self, language_token_id: int) -> None:
        self.language_token_id = language_token_id
        self.generation_config = type(
            "GenerationConfig",
            (),
            {"language": "mongolian", "lang_to_id": {"<|mn|>": 41, "<|en|>": 42, "<|fr|>": 99}},
        )()
        self.detect_kwargs: dict[str, object] = {}

    def detect_language(self, **kwargs):
        self.detect_kwargs = kwargs
        return torch.tensor([self.language_token_id])


@pytest.mark.parametrize("language_token_id, expected_language", [(41, "mn"), (42, "en")])
def test_auto_detection_uses_whisper_detector_tokens(
    language_token_id: int,
    expected_language: str,
):
    engine = STTEngine(load_config(), language="auto")
    model = AutoDetectModel(language_token_id)
    engine._processor = AutoDetectProcessor()
    engine._model = model
    engine.loaded = True

    detected = engine.detect_language(np.zeros(16_000, dtype=np.float32))

    assert detected == expected_language
    assert model.detect_kwargs["generation_config"].language is None


def test_auto_detection_restricts_whisper_to_mongolian_and_english():
    engine = STTEngine(load_config(), language="auto")
    engine._processor = AutoDetectProcessor()
    model = AutoDetectModel(99)
    engine._model = model
    engine.loaded = True

    with pytest.raises(STTError, match="could not detect Mongolian or English"):
        engine.detect_language(np.zeros(16_000, dtype=np.float32))

    assert model.detect_kwargs["generation_config"].lang_to_id == {"<|mn|>": 41, "<|en|>": 42}


def test_auto_detector_uses_neutral_whisper_model_configuration():
    config = load_config()

    assert config.stt_auto_model_id == "openai/whisper-tiny"
    assert config.stt_auto_local_path.name == "whisper-tiny-auto"


def test_desktop_language_defaults_to_auto():
    assert load_config().desktop_language == "auto"
