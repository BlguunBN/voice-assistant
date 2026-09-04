from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile

from src.core.config import AppConfig


class EdgeTTSError(RuntimeError):
    """Raised when Microsoft Edge TTS cannot generate Mongolian audio."""


class EdgeMongolianTTSEngine:
    """TTS engine backed by the free Microsoft Edge Mongolian voice."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.loaded = False

    def load(self) -> None:
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:
            raise EdgeTTSError("Install edge-tts with: python -m pip install edge-tts") from exc
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def voices(self) -> list[str]:
        self.load()
        return [self.config.tts_edge_voice]

    async def _save(self, text: str, output: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(
            text=text.strip(),
            voice=self.config.tts_edge_voice,
            rate=self.config.tts_edge_rate,
            volume=self.config.tts_edge_volume,
            pitch=self.config.tts_edge_pitch,
        ).save(str(output))

    def synthesize(
        self,
        text: str,
        speaker_id: str | None = None,
        output_path: str | Path | None = None,
    ) -> Path:
        """Generate an MP3 file using the configured Mongolian Edge voice."""
        self.load()
        if not text or not text.strip():
            raise EdgeTTSError("TTS text must not be empty")
        if speaker_id and speaker_id != self.config.tts_edge_voice:
            raise EdgeTTSError(
                f"Unknown Edge voice {speaker_id!r}; available: {self.config.tts_edge_voice}"
            )

        if output_path is None:
            cache = self.config.project_root / "cache"
            cache.mkdir(parents=True, exist_ok=True)
            handle, generated = tempfile.mkstemp(suffix=".mp3", prefix="tts-", dir=cache)
            output = Path(generated)
            output.unlink(missing_ok=True)
        else:
            output = Path(output_path).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.suffix.lower() != ".mp3":
                output = output.with_suffix(".mp3")

        try:
            asyncio.run(self._save(text, output))
        except Exception as exc:
            output.unlink(missing_ok=True)
            if isinstance(exc, EdgeTTSError):
                raise
            raise EdgeTTSError(f"Edge TTS synthesis failed: {exc}") from exc
        if not output.is_file() or output.stat().st_size == 0:
            raise EdgeTTSError(f"Edge TTS did not create a valid output file: {output}")
        return output