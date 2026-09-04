from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import numpy as np
import soundfile as sf

from src.audio.capture import Recording
from src.audio.devices import AudioDevice, AudioDeviceManager
from src.audio.hotkey import KeyChord
from src.core.config import AppConfig
from src.desktop.injector import ClipboardTextInjector
from src.desktop.overlay import DesktopOverlayHost, OverlayHostError
from src.desktop.preferences import DesktopPreferencesStore
from src.desktop.status import DesktopStatusStore

LOGGER = logging.getLogger(__name__)


class DesktopDictationError(RuntimeError):
    """Raised when the desktop dictation companion cannot complete a turn."""


@dataclass(frozen=True)
class DesktopRecorder:
    """Capture one hold-to-talk recording from a globally polled key chord."""

    device: AudioDevice
    sample_rate: int
    max_seconds: float
    blocksize: int
    hotkey: KeyChord
    poll_interval_seconds: float = 0.01

    def _sounddevice(self) -> Any:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise DesktopDictationError("sounddevice is required for desktop dictation") from exc
        return sd

    def _wait_for_release(self) -> None:
        while self.hotkey.is_down():
            time.sleep(self.poll_interval_seconds)

    def _wait_for_press(self) -> None:
        while not self.hotkey.is_down():
            time.sleep(self.poll_interval_seconds)

    def record(self, on_started: Callable[[], None] | None = None) -> Recording:
        """Wait for the chord, capture while held, and return mono float32 audio."""
        self._wait_for_release()
        self._wait_for_press()
        if on_started is not None:
            on_started()
        chunks: list[np.ndarray] = []
        statuses: list[str] = []

        def callback(indata: np.ndarray, frames: int, callback_time: Any, status: Any) -> None:
            del frames, callback_time
            if status:
                statuses.append(str(status))
            chunks.append(indata[:, 0].copy())

        started_at = time.perf_counter()
        try:
            with self._sounddevice().InputStream(
                samplerate=self.sample_rate,
                device=self.device.index,
                channels=1,
                dtype="float32",
                blocksize=self.blocksize,
                callback=callback,
            ):
                while self.hotkey.is_down():
                    if time.perf_counter() - started_at >= self.max_seconds:
                        break
                    time.sleep(self.poll_interval_seconds)
        except Exception as exc:
            raise DesktopDictationError(f"Microphone capture failed: {exc}") from exc

        if statuses:
            LOGGER.warning("Desktop microphone stream status: %s", "; ".join(statuses))
        if not chunks:
            raise DesktopDictationError("Microphone returned no audio frames")
        ended_at = time.perf_counter()
        return Recording(
            samples=np.concatenate(chunks).astype(np.float32, copy=False),
            sample_rate=self.sample_rate,
            started_at=started_at,
            ended_at=ended_at,
            device=self.device,
        )


class DesktopDictation:
    """Run global push-to-talk dictation and paste the result into the focused app."""

    def __init__(
        self,
        config: AppConfig,
        *,
        injector: ClipboardTextInjector | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.injector = injector or ClipboardTextInjector()
        self.status_callback = status_callback
        self._stop = threading.Event()
        self._icon: Any = None
        self._last_detected_language: str | None = None
        self.status_store = DesktopStatusStore(config.project_root / "cache" / "desktop-status.json")
        self.preferences_store = DesktopPreferencesStore(config.project_root / "cache" / "desktop-preferences.json")
        self.overlay_host = DesktopOverlayHost(
            self.status_store.path,
        )
        manager = AudioDeviceManager(input_device=config.audio_input_device)
        input_device = manager.selected("input")
        self.recorder = DesktopRecorder(
            device=input_device,
            sample_rate=config.audio_sample_rate,
            max_seconds=config.audio_max_seconds,
            blocksize=config.audio_blocksize,
            hotkey=KeyChord.parse(config.desktop_hotkey),
        )

    @property
    def transcribe_url(self) -> str:
        return f"http://{self.config.api_host}:{self.config.api_port}/stt"

    def _selected_language(self) -> str:
        store = getattr(self, "preferences_store", None)
        if store is not None:
            return store.read().selected_language
        return self.config.desktop_language

    def _set_status(
        self,
        value: str,
        *,
        transcript: str | None = None,
        detected_language: str | None = None,
    ) -> None:
        status = value
        detail: str | None = None
        if value.startswith("error:"):
            status, _, detail = value.partition(":")
            detail = detail.strip()
        if detected_language is not None:
            self._last_detected_language = detected_language
        self.status_store.update(
            status,
            transcript=transcript,
            detail=detail,
            selected_language=self._selected_language(),
            detected_language=getattr(self, "_last_detected_language", None),
        )
        if self.status_callback is not None:
            self.status_callback(value)
        if self._icon is not None:
            self._icon.title = f"Mongolian Dictation — {value}"

    def run(self) -> None:
        """Start the tray icon and background global dictation loop."""
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as exc:
            raise DesktopDictationError(
                "Desktop mode requires pystray and Pillow; install project requirements first"
            ) from exc

        image = Image.new("RGB", (64, 64), "#10243e")
        ImageDraw.Draw(image).rounded_rectangle((8, 8, 56, 56), radius=12, fill="#56d6c9")
        icon = pystray.Icon(
            "mongolian-voice-assistant",
            image,
            "Mongolian Dictation — armed",
            menu=pystray.Menu(
                pystray.MenuItem("Show overlay", self._show_overlay),
                pystray.MenuItem("Open control panel", self._open_control_panel),
                pystray.MenuItem("Quit", self._quit),
            ),
        )
        self._icon = icon
        self.status_store.clear()
        try:
            self.overlay_host.start()
        except OverlayHostError as exc:
            LOGGER.warning("Desktop overlay unavailable: %s", exc)
        self._set_status("armed")
        worker = threading.Thread(target=self._loop, name="desktop-dictation", daemon=True)
        worker.start()
        try:
            icon.run()
        finally:
            self._stop.set()
            worker.join(timeout=2)
            self.overlay_host.stop()
            self._icon = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                recording = self.recorder.record(on_started=self._on_recording_started)
                if self._stop.is_set():
                    break
                self._process_recording(recording)
            except Exception as exc:
                LOGGER.exception("Desktop dictation turn failed")
                self._set_status(f"error: {exc}")
                time.sleep(1)
            finally:
                if not self._stop.is_set():
                    self._set_status("armed")

    def _process_recording(self, recording: Recording) -> None:
        self._set_status("transcribing")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            audio_path = Path(handle.name)
        try:
            sf.write(audio_path, recording.samples, recording.sample_rate, format="WAV")
            transcript = self._transcribe(audio_path)
            if not transcript:
                raise DesktopDictationError("Speech recognition returned empty text")
            self._set_status("pasting", transcript=transcript)
            self.injector.paste(transcript)
        finally:
            audio_path.unlink(missing_ok=True)

    def _transcribe(self, audio_path: Path) -> str:
        boundary = "----VoiceAssistantBoundary"
        audio = audio_path.read_bytes()
        selected_language = self._selected_language()
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="language"\r\n\r\n'
            f"{selected_language}\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="dictation.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + audio + f"\r\n--{boundary}--\r\n".encode("ascii")
        request = urllib_request.Request(
            self.transcribe_url,
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib_request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DesktopDictationError(f"STT API request failed: {exc}") from exc
        transcript = payload.get("transcript")
        if not isinstance(transcript, str):
            raise DesktopDictationError("STT API returned an invalid transcript")
        detected_language = payload.get("detected_language")
        if detected_language in {"mn", "en"}:
            self._last_detected_language = detected_language
        elif selected_language in {"mn", "en"}:
            self._last_detected_language = selected_language
        else:
            self._last_detected_language = None
        return transcript.strip()

    def _on_recording_started(self) -> None:
        self._set_status("listening", transcript="")

    def _show_overlay(self, icon: Any, item: Any) -> None:
        del icon, item
        self.overlay_host.show()

    @staticmethod
    def _open_control_panel(icon: Any, item: Any) -> None:
        del icon, item
        webbrowser.open("http://127.0.0.1:5173/")

    def _quit(self, icon: Any, item: Any) -> None:
        del item
        self._stop.set()
        icon.stop()
