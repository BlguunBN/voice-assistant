"""Mongolian Whisper model entry point.

The implementation stays in :mod:`src.stt.engine` so future STT backends can
share the lifecycle and audio contract without changing the CLI.
"""

from .engine import STTError, STTEngine

MODEL_ID = "Blgn94/whisper-small-mn-v3"

__all__ = ["MODEL_ID", "STTError", "STTEngine"]
