from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.config import ConfigError, load_config
from src.stt.engine import STTEngine, STTError


class FakeProcessor:
    def __call__(self, audio, *, sampling_rate, return_tensors):
        assert sampling_rate == 16_000
        assert return_tensors == "pt"
        import torch

        return {"input_features": torch.zeros((1, 80, 3000))}

    def batch_decode(self, generated_ids, *, skip_special_tokens):
        assert skip_special_tokens is True
        return [" Монгол хэлний тест "]


class FakeModel:
    def eval(self):
        return self

    def to(self, device):
        assert device == "cpu"
        return self

    def generate(self, **inputs):
        import torch

        assert "input_features" in inputs
        return torch.tensor([[1, 2, 3]])


def test_default_config_keeps_models_and_cache_on_d_drive():
    config = load_config()

    assert config.stt_model_id == "Blgn94/whisper-small-mn-v3"
    assert str(config.stt_local_path).upper().startswith("D:\\AI\\MODELS")
    assert str(config.huggingface_cache).upper().startswith("D:\\AI\\HUGGINGFACE")
    assert config.stt_sample_rate == 16_000


def test_invalid_language_is_rejected(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        system: {language: en}
        storage:
          project_root: D:/AI/voice-assistant
          model_root: D:/AI/models
          recordings: D:/AI/recordings
          huggingface_home: D:/AI/huggingface
          huggingface_cache: D:/AI/huggingface/hub
        stt:
          model: test/model
          local_path: D:/AI/models/stt/test
          device: cuda
          fallback_device: cpu
          sample_rate: 16000
          max_new_tokens: 10
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="system.language"):
        load_config(config_path)


def test_audio_is_resampled_to_mono_16khz(tmp_path: Path):
    import soundfile as sf

    config = load_config()
    engine = STTEngine(config)
    source = np.ones((8000, 2), dtype=np.float32)
    path = tmp_path / "input.wav"
    sf.write(path, source, 8000)

    samples = engine._read_audio(path)

    assert samples.dtype == np.float32
    assert samples.ndim == 1
    assert samples.shape == (16_000,)
    assert np.allclose(samples, 1.0, atol=1e-4)


def test_transcribe_returns_decoded_text_with_injected_engine():
    config = load_config()
    engine = STTEngine(config)
    engine._processor = FakeProcessor()
    engine._model = FakeModel()
    engine.device = "cpu"
    engine.loaded = True

    result = engine.transcribe(np.zeros(16_000, dtype=np.float32))

    assert result == "Монгол хэлний тест"
    assert engine.last_latency_seconds is not None


def test_missing_audio_is_readable_error():
    config = load_config()
    engine = STTEngine(config)
    engine._processor = FakeProcessor()
    engine._model = FakeModel()
    engine.device = "cpu"
    engine.loaded = True

    with pytest.raises(STTError, match="Audio file not found"):
        engine.transcribe("missing.wav")
