from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import src.desktop.dictation as dictation_module
from src.audio.hotkey import HotkeyError, KeyChord
from src.core.config import load_config
from src.desktop.dictation import DesktopDictation
from src.desktop.injector import ClipboardTextInjector
def test_desktop_hotkey_parses_ctrl_shift_space():
    chord = KeyChord.parse("Ctrl + Shift + Space")

    assert chord.keys == ("ctrl", "shift", "space")
    assert chord.label == "ctrl+shift+space"


def test_desktop_hotkey_rejects_unsupported_keys():
    with pytest.raises(HotkeyError, match="Unsupported push-to-talk key"):
        KeyChord.parse("ctrl+f1")


def test_config_exposes_desktop_dictation_defaults():
    config = load_config()

    assert config.desktop_hotkey == "win+alt"
    assert config.desktop_language == "auto"


def test_desktop_transcribe_posts_multipart_audio(monkeypatch, tmp_path: Path):
    config = load_config()
    engine = object.__new__(DesktopDictation)
    engine.config = config
    audio_path = tmp_path / "dictation.wav"
    audio_path.write_bytes(b"RIFF-test")
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return '{"transcript":"Сайн байна уу","detected_language":"en"}'.encode()

    def fake_urlopen(request: Any, timeout: int):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(dictation_module.urllib_request, "urlopen", fake_urlopen)

    assert engine._transcribe(audio_path) == "Сайн байна уу"
    assert engine._last_detected_language == "en"
    request = captured["request"]
    assert request.full_url.endswith("/stt")
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="language"' in request.data
    assert b"\r\nauto\r\n" in request.data
    assert b"dictation.wav" in request.data
    assert b"RIFF-test" in request.data

def test_desktop_error_status_truncates_tray_title():
    engine = object.__new__(DesktopDictation)
    engine.config = load_config()
    updates: dict[str, Any] = {}

    class FakeStatusStore:
        def update(self, status: str, **kwargs: Any) -> None:
            updates["status"] = status
            updates.update(kwargs)

    class FakeIcon:
        title = ""

    engine.status_store = FakeStatusStore()
    engine.status_callback = None
    engine._icon = FakeIcon()

    error = "error: STT API request failed: " + "x" * 200
    engine._set_status(error)

    assert len(engine._icon.title) <= 128
    assert updates["status"] == "error"
    assert updates["detail"] == error.removeprefix("error: ").strip()

def test_clipboard_injector_restores_previous_text(monkeypatch):
    import ctypes

    clipboard = {"value": "old"}
    events: list[tuple[int, int]] = []

    class FakeUser32:
        def GetForegroundWindow(self):
            return 7

        def keybd_event(self, key, scan_code, flags, extra):
            del scan_code, extra
            events.append((key, flags))

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=FakeUser32()), raising=False)
    monkeypatch.setitem(
        sys.modules,
        "pyperclip",
        SimpleNamespace(paste=lambda: clipboard["value"], copy=lambda value: clipboard.update(value=value)),
    )

    ClipboardTextInjector(paste_delay_seconds=0).paste("new text")

    assert clipboard["value"] == "old"
    assert events == [(0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)]
def test_clipboard_injector_restores_captured_window_before_paste(monkeypatch):
    import ctypes

    clipboard = {"value": "old"}
    events: list[tuple[str, int]] = []

    class FakeUser32:
        foreground = 7

        def GetForegroundWindow(self):
            return self.foreground

        def SetForegroundWindow(self, target_window):
            events.append(("focus", target_window))
            self.foreground = target_window
            return 1

        def keybd_event(self, key, scan_code, flags, extra):
            del scan_code, extra
            events.append(("key", key if flags == 0 else -key))

    user32 = FakeUser32()
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)
    monkeypatch.setitem(
        sys.modules,
        "pyperclip",
        SimpleNamespace(paste=lambda: clipboard["value"], copy=lambda value: clipboard.update(value=value)),
    )

    user32.foreground = 99
    ClipboardTextInjector(paste_delay_seconds=0).paste("new text", target_window=7)

    assert clipboard["value"] == "old"
    assert events[0] == ("focus", 7)
    assert events[1:] == [("key", 17), ("key", 86), ("key", -86), ("key", -17)]


def test_desktop_loop_accepts_two_consecutive_recordings():
    config = load_config()
    engine = object.__new__(DesktopDictation)
    engine.config = config
    engine._stop = dictation_module.threading.Event()
    engine._set_status = lambda *_args, **_kwargs: None
    targets = iter((101, 202))
    focused_windows: list[int] = []

    class FakeInjector:
        def focused_window(self):
            target = next(targets)
            focused_windows.append(target)
            return target

    class FakeRecorder:
        def __init__(self):
            self.calls = 0

        def record(self, on_started=None):
            self.calls += 1
            if on_started is not None:
                on_started()
            return f"recording-{self.calls}"

    processed: list[tuple[str, int]] = []
    engine.injector = FakeInjector()
    engine.recorder = FakeRecorder()

    def process(recording, *, target_window=None):
        processed.append((recording, target_window))
        if len(processed) == 2:
            engine._stop.set()

    engine._process_recording = process
    engine._loop()

    assert focused_windows == [101, 202]
    assert processed == [("recording-1", 101), ("recording-2", 202)]
