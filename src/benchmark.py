from __future__ import annotations

from pathlib import Path
import tempfile
import time
from typing import Any

import soundfile as sf

from src.core.config import AppConfig
from src.stt import STTEngine
from src.tts import TTSEngine


def _default_audio(config: AppConfig) -> Path:
    preferred = config.recordings_root / "input" / "common_voice_mn_18577346.wav"
    if preferred.is_file():
        return preferred
    candidates = sorted(config.recordings_root.rglob("*.wav"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        f"No WAV benchmark input found under {config.recordings_root}; pass benchmark --audio PATH"
    )


def _memory_snapshot() -> dict[str, float | None]:
    import psutil

    process = psutil.Process()
    snapshot: dict[str, float | None] = {
        "rss_gib": process.memory_info().rss / 1024**3,
        "cuda_allocated_mib": None,
        "cuda_peak_allocated_mib": None,
    }
    try:
        import torch

        if torch.cuda.is_available():
            snapshot["cuda_allocated_mib"] = torch.cuda.memory_allocated() / 1024**2
            snapshot["cuda_peak_allocated_mib"] = torch.cuda.max_memory_allocated() / 1024**2
    except ImportError:
        pass
    return snapshot


def run_benchmark(config: AppConfig, audio_path: str | Path | None = None, iterations: int = 3) -> dict[str, Any]:
    """Measure resident Transformers STT and CPU TTS without playing audio."""
    if iterations < 1:
        raise ValueError("benchmark iterations must be positive")
    input_path = Path(audio_path).expanduser().resolve() if audio_path else _default_audio(config)
    if not input_path.is_file():
        raise FileNotFoundError(f"Benchmark audio not found: {input_path}")

    stt = STTEngine(config)
    tts = TTSEngine(config)
    stt_times: list[float] = []
    tts_times: list[float] = []
    durations: list[float] = []
    transcripts: list[str] = []
    stt_load_started = time.perf_counter()
    try:
        stt.load()
        stt_load_seconds = time.perf_counter() - stt_load_started
        tts_load_started = time.perf_counter()
        tts.load()
        tts_load_seconds = time.perf_counter() - tts_load_started
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
        except ImportError:
            pass

        with tempfile.TemporaryDirectory(dir=config.project_root / "cache") as output_dir:
            for _ in range(iterations):
                started = time.perf_counter()
                transcript = stt.transcribe(input_path)
                stt_times.append(time.perf_counter() - started)
                transcripts.append(transcript)

                output_path = Path(output_dir) / "benchmark.wav"
                started = time.perf_counter()
                tts.synthesize(transcript, output_path=output_path)
                tts_times.append(time.perf_counter() - started)
                info = sf.info(output_path)
                durations.append(info.frames / info.samplerate)

        memory = _memory_snapshot()
        return {
            "audio": str(input_path),
            "iterations": iterations,
            "transcripts_identical": len(set(transcripts)) == 1,
            "stt_load_seconds": round(stt_load_seconds, 3),
            "tts_load_seconds": round(tts_load_seconds, 3),
            "average_stt_seconds": round(sum(stt_times) / iterations, 3),
            "average_tts_seconds": round(sum(tts_times) / iterations, 3),
            "average_total_seconds": round((sum(stt_times) + sum(tts_times)) / iterations, 3),
            "average_audio_duration_seconds": round(sum(durations) / iterations, 3),
            "stt_device": stt.device,
            "detected_language": stt.last_detected_language,
            "stt_real_time_factor": round(stt.last_real_time_factor, 3) if stt.last_real_time_factor is not None else None,
            "stt_peak_vram_mib": round(stt.last_peak_vram_bytes / 1024**2, 1) if stt.last_peak_vram_bytes is not None else None,
            "tts_device": config.tts_device,
            "memory": memory,
        }
    finally:
        stt.unload()
        tts.unload()
