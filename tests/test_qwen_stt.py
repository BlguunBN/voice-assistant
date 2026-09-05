from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from src.core.config import load_config
from src.stt.qwen import QwenSTTEngine


class _Inputs(dict[str, torch.Tensor]):
    def to(self, *_args, **_kwargs):
        return self


class _Processor:
    def __init__(self) -> None:
        self.audio: object | None = None

    def apply_transcription_request(self, *, audio, language):
        self.audio = audio
        assert language == "English"
        return _Inputs(input_ids=torch.tensor([[1, 2]]))

    def decode(self, _ids, *, return_format):
        assert return_format == "parsed"
        return [{"language": "English", "transcription": "Hello world"}]


class _Model:
    dtype = torch.float32

    def generate(self, **_kwargs):
        return torch.tensor([[1, 2, 3]])


def test_qwen_decodes_local_audio_before_calling_the_processor(tmp_path: Path):
    path = tmp_path / "english.wav"
    sf.write(path, np.ones((8_000, 2), dtype=np.float32), 8_000)
    engine = QwenSTTEngine(load_config())
    processor = _Processor()
    engine._processor, engine._model, engine.loaded, engine.device = processor, _Model(), True, "cpu"

    assert engine.transcribe(path, language="en") == "Hello world"
    assert isinstance(processor.audio, np.ndarray)
    assert processor.audio.shape == (16_000,)
    assert engine.last_detected_language == "en"
