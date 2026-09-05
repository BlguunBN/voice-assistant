from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.agent import EchoAgent
from src.audio import (
    AudioDeviceError,
    AudioDeviceManager,
    AudioGate,
    AudioPlayback,
    AudioRecorder,
    VADConfig,
)
from src.core.config import AppConfig, ConfigError, load_config
from src.pipeline import EchoPipeline
from src.stt.engine import STTError
from src.stt.router import STTLanguageRouter
from src.tts.engine import TTSEngine, TTSError

LOGGER = logging.getLogger(__name__)


def configure_logging(config: AppConfig, log_name: str = "voice-assistant.log") -> None:
    log_path = config.project_root / "logs" / log_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_handler = logging.FileHandler(log_path, encoding="utf-8")
    except PermissionError:
        log_handler = logging.StreamHandler()
    logging.basicConfig(
        handlers=[log_handler],
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


def _torch_status() -> tuple[str, str, int | None]:
    try:
        import torch
    except ImportError:
        return "not installed", "unavailable", None
    if not torch.cuda.is_available():
        return torch.__version__, "unavailable", None
    properties = torch.cuda.get_device_properties(0)
    return torch.__version__, torch.cuda.get_device_name(0), int(properties.total_memory)


def _audio_manager(config: AppConfig) -> AudioDeviceManager:
    return AudioDeviceManager(
        input_device=config.audio_input_device,
        output_device=config.audio_output_device,
    )


def _print_audio_devices(config: AppConfig) -> tuple[AudioDeviceManager, object, object]:
    manager = _audio_manager(config)
    selected_input, selected_output, devices = manager.describe()
    print("Audio")
    print(f"  selected input: {selected_input.label()}")
    print(f"  selected output: {selected_output.label()}")
    print(f"  sample rate: {config.audio_sample_rate} Hz")
    print(f"  push-to-talk: {config.push_to_talk_hotkey}")
    print(f"  VAD: {'enabled' if config.vad_enabled else 'disabled'}")
    print("  detected devices:")
    for device in devices:
        print(f"    {device.label()}")
    return manager, selected_input, selected_output


def print_status(config: AppConfig) -> None:
    torch_version, gpu_name, vram = _torch_status()
    mongolian_stt_path = config.stt_mongolian_local_path
    english_stt_path = config.stt_english_local_path
    tts_path = config.tts_local_path
    print("STT models")
    print(f"  Mongolian: {config.stt_mongolian_model_id}")
    print(f"    path: {mongolian_stt_path}")
    print(f"    installation: {'installed' if mongolian_stt_path.is_dir() else 'missing'}")
    print(f"  English: {config.stt_english_model_id}")
    print(f"    path: {english_stt_path}")
    print(f"    installation: {'installed' if english_stt_path.is_dir() else 'missing'}")
    print("  load status: lazy; only the active language model remains resident")
    print(f"  configured device: {config.stt_device}")
    print(f"  fallback device: {config.stt_fallback_device}")
    print("TTS model")
    print(f"  repository: {config.tts_model_id}")
    print(f"  path: {tts_path}")
    print(f"  installation status: {'installed' if tts_path.is_dir() else 'missing'}")
    print("  load status: not loaded (run voices or speak to load once)")
    print(f"  configured device: {config.tts_device}")
    print("PyTorch")
    print(f"  version: {torch_version}")
    print(f"  CUDA/GPU: {gpu_name}")
    if vram is not None:
        print(f"  VRAM: {vram / (1024**3):.2f} GiB")
    print(f"Hugging Face cache: {config.huggingface_cache}")
    _print_audio_devices(config)


def transcribe(config: AppConfig, audio_path: str, language: str) -> int:
    engine = STTLanguageRouter(config)
    try:
        result = engine.transcribe(Path(audio_path), language=language)
        print(result)
        if engine.last_latency_seconds is not None:
            LOGGER.info(
                "CLI transcription completed path=%s latency_seconds=%.3f device=%s",
                audio_path,
                engine.last_latency_seconds,
                engine.device,
            )
        return 0
    finally:
        engine.unload()


def voices(config: AppConfig) -> int:
    engine = TTSEngine(config)
    try:
        for speaker in engine.voices():
            print(speaker)
        return 0
    finally:
        engine.unload()


def speak(config: AppConfig, text: str, speaker_id: str | None, output_path: str | None) -> int:
    engine = TTSEngine(config)
    try:
        output = engine.speak(text, speaker_id=speaker_id, output_path=output_path)
        print(output if output_path else "speech generated and played")
        return 0
    finally:
        engine.unload()


def _pipeline(config: AppConfig) -> tuple[EchoPipeline, STTLanguageRouter, TTSEngine, object, object]:
    manager = _audio_manager(config)
    selected_input = manager.selected("input")
    selected_output = manager.selected("output")
    stt = STTLanguageRouter(config)
    tts = TTSEngine(config)
    gate = AudioGate()
    vad = (
        VADConfig(
            start_threshold=config.vad_start_threshold,
            stop_threshold=config.vad_stop_threshold,
            silence_seconds=config.vad_silence_seconds,
            min_speech_seconds=config.vad_min_speech_seconds,
        )
        if config.vad_enabled
        else None
    )
    recorder = AudioRecorder(
        device=selected_input,
        sample_rate=config.audio_sample_rate,
        max_seconds=config.audio_max_seconds,
        blocksize=config.audio_blocksize,
        hotkey=config.push_to_talk_hotkey,
        vad=vad,
        gate=gate,
    )
    playback = AudioPlayback(config, selected_output, tts=tts)
    pipeline = EchoPipeline(recorder, stt, EchoAgent(), playback, gate=gate)
    return pipeline, stt, tts, selected_input, selected_output


def listen(config: AppConfig, turns: int) -> int:
    pipeline, _, _, selected_input, selected_output = _pipeline(config)
    try:
        print(f"Selected input device: {selected_input.label()}")
        print(f"Selected output device: {selected_output.label()}")
        for turn_index in range(1, turns + 1):
            recording, transcript, transitions = pipeline.listen_once()
            print(f"Turn {turn_index} recognized text: {transcript}")
            print(f"Recording duration: {recording.duration_seconds:.3f} s")
            print("State transitions: " + " -> ".join(state.value for state in transitions))
        return 0
    finally:
        pipeline.shutdown()


def echo(config: AppConfig, speaker_id: str | None, turns: int) -> int:
    pipeline, _, _, selected_input, selected_output = _pipeline(config)
    try:
        print(f"Selected input device: {selected_input.label()}")
        print(f"Selected output device: {selected_output.label()}")
        for turn_index in range(1, turns + 1):
            turn = pipeline.echo_once(speaker_id=speaker_id)
            print(f"Turn {turn_index} recognized text: {turn.transcript}")
            print(f"Echo response: {turn.response}")
            print("TTS result: played")
            print("State transitions: " + " -> ".join(state.value for state in turn.state_transitions))
            print(f"STT latency: {turn.stt_latency_seconds:.3f} s")
            print(f"TTS latency: {turn.tts_latency_seconds:.3f} s")
            print(f"End-of-speech to audio start: {turn.end_of_speech_to_audio_start_seconds:.3f} s")
        return 0
    finally:
        pipeline.shutdown()


def benchmark(config: AppConfig, audio_path: str | None, iterations: int) -> int:
    import json

    from src.benchmark import run_benchmark

    result = run_benchmark(config, audio_path=audio_path, iterations=iterations)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def serve_api(config: AppConfig) -> int:
    from src.api.server import serve

    serve(config)
    return 0



def desktop(config: AppConfig) -> int:
    from src.desktop.dictation import DesktopDictation

    DesktopDictation(config).run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Mongolian voice assistant")
    parser.add_argument("--config", default=None, help="Path to YAML configuration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show local models, audio devices, and hardware status")
    subparsers.add_parser("voices", help="List speakers discovered from the TTS model")

    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe a WAV/audio file")
    transcribe_parser.add_argument("audio", help="Path to the audio file")
    transcribe_parser.add_argument("--language", choices=("mn", "en", "auto"), default="mn")

    speak_parser = subparsers.add_parser("speak", help="Generate and play Mongolian speech")
    speak_parser.add_argument("--speaker", dest="speaker_id", default=None)
    speak_parser.add_argument("--output", dest="output_path", default=None)
    speak_parser.add_argument("text", help="Mongolian text to speak")

    listen_parser = subparsers.add_parser("listen", help="Record and transcribe push-to-talk turns")
    listen_parser.add_argument("--turns", type=int, default=1)

    echo_parser = subparsers.add_parser("echo", help="Run push-to-talk STT-to-TTS echo turns")
    echo_parser.add_argument("--speaker", dest="speaker_id", default=None)
    echo_parser.add_argument("--turns", type=int, default=1)

    benchmark_parser = subparsers.add_parser("benchmark", help="Benchmark resident STT and TTS models")
    benchmark_parser.add_argument("--audio", dest="audio_path", default=None)
    benchmark_parser.add_argument("--iterations", type=int, default=3)

    subparsers.add_parser("desktop", help="Run the global desktop dictation tray companion")
    subparsers.add_parser("api", help="Run the localhost FastAPI service")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        configure_logging(config, "voice-assistant-desktop.log" if args.command == "desktop" else "voice-assistant.log")
        if args.command == "status":
            print_status(config)
            return 0
        if args.command == "transcribe":
            return transcribe(config, args.audio, args.language)
        if args.command == "voices":
            return voices(config)
        if args.command == "speak":
            return speak(config, args.text, args.speaker_id, args.output_path)
        if args.command == "listen":
            if args.turns < 1:
                raise ConfigError("listen --turns must be positive")
            return listen(config, args.turns)
        if args.command == "echo":
            if args.turns < 1:
                raise ConfigError("echo --turns must be positive")
            return echo(config, args.speaker_id, args.turns)
        if args.command == "benchmark":
            if args.iterations < 1:
                raise ConfigError("benchmark --iterations must be positive")
            return benchmark(config, args.audio_path, args.iterations)
        if args.command == "desktop":
            return desktop(config)
        if args.command == "api":
            return serve_api(config)
        raise ConfigError(f"Unsupported command: {args.command}")
    except (AudioDeviceError, ConfigError, STTError, TTSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
