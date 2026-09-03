from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from src.core.config import load_config
from src.tts.engine import TTSError, TTSEngine


class FakeTTS:
    def tts_to_file(self, *, text, speaker, file_path, split_sentences):
        assert text == "Сайн байна уу."
        assert speaker == "spk_0001"
        assert split_sentences is True
        sf.write(file_path, np.zeros(2205, dtype=np.float32), 22050)
        return file_path


def test_voices_are_sorted_by_actual_model_index():
    engine = TTSEngine(load_config())
    engine.loaded = True
    engine._speakers = {"spk_0002": 1, "spk_0001": 0}

    assert engine.voices() == ["spk_0001", "spk_0002"]


def test_synthesize_writes_valid_wav_and_records_duration(tmp_path: Path):
    engine = TTSEngine(load_config())
    engine.loaded = True
    engine._speakers = {"spk_0001": 0}
    engine._tts = FakeTTS()
    output = tmp_path / "tts.wav"

    result = engine.synthesize("Сайн байна уу.", output_path=output)

    info = sf.info(result)
    assert result == output
    assert info.samplerate == 22050
    assert info.frames == 2205
    assert engine.last_synthesis_seconds is not None
    assert engine.last_audio_duration_seconds == pytest.approx(0.1)


def test_unknown_speaker_is_rejected():
    engine = TTSEngine(load_config())
    engine.loaded = True
    engine._speakers = {"spk_0001": 0}

    with pytest.raises(TTSError, match="Unknown speaker"):
        engine._speaker("missing")
