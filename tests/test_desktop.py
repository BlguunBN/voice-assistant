from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import src.desktop.dictation as dictation_module
from src.audio.hotkey import HotkeyError, KeyChord
from src.core.config import load_config
from src.desktop.dictation import DesktopDictation, DesktopDictationError, DesktopInstanceLock
from src.desktop.injector import ClipboardTextInjector
def test_desktop_hotkey_parses_ctrl_shift_space():
    chord = KeyChord.parse("Ctrl + Shift + Space")

    assert chord.keys == ("ctrl", "shift", "space")
    assert chord.label == "ctrl+shift+space"


def test_desktop_hotkey_rejects_unsupported_keys():
    with pytest.raises(HotkeyError, match="Unsupported push-to-talk key"):
        KeyChord.parse("ctrl+f1")


def test_desktop_instance_lock_allows_relaunch_after_release(monkeypatch):
    import ctypes

    class FakeFunction:
        def __init__(self, callback):
            self.callback = callback

        def __call__(self, *args):
            return self.callback(*args)

    class FakeKernel32:
        def __init__(self):
            self.active_handles: set[int] = set()
            self.next_handle = 40
            self.closed: list[int] = []
            self.CreateMutexW = FakeFunction(self.create_mutex)
            self.CloseHandle = FakeFunction(self.close_handle)

        def create_mutex(self, *_args):
            already_exists = bool(self.active_handles)
            self.next_handle += 1
            handle = self.next_handle
            self.active_handles.add(handle)
            monkeypatch.setattr(ctypes, "get_last_error", lambda: 183 if already_exists else 0)
            return handle

        def close_handle(self, handle):
            self.closed.append(handle)
            self.active_handles.discard(handle)

    kernel32 = FakeKernel32()
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel32, raising=False)

    first = DesktopInstanceLock()
    first.acquire()
    with pytest.raises(DesktopDictationError, match="already running"):
        DesktopInstanceLock().acquire()
    first.release()

    relaunched = DesktopInstanceLock()
    relaunched.acquire()
    relaunched.release()

    assert kernel32.closed == [42, 41, 43]


def test_config_exposes_desktop_dictation_defaults():
    config = load_config()

    assert config.desktop_hotkey == "ctrl+alt"
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

    ClipboardTextInjector(paste_delay_seconds=0, clipboard_restore_delay_seconds=0).paste("new text")

    assert clipboard["value"] == "old"
    assert events == [(0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)]


def test_clipboard_injector_waits_for_target_to_consume_paste_before_restoring(monkeypatch):
    import ctypes

    clipboard = {"value": "old"}
    pauses: list[float] = []
    consumed: list[str] = []

    class FakeUser32:
        def GetForegroundWindow(self):
            return 7

        def keybd_event(self, *_args):
            return None

    def sleep(seconds: float) -> None:
        pauses.append(seconds)
        if seconds == 0.4:
            consumed.append(clipboard["value"])

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=FakeUser32()), raising=False)
    monkeypatch.setattr("src.desktop.injector.time.sleep", sleep)
    monkeypatch.setitem(
        sys.modules,
        "pyperclip",
        SimpleNamespace(paste=lambda: clipboard["value"], copy=lambda value: clipboard.update(value=value)),
    )

    ClipboardTextInjector(paste_delay_seconds=0.01, clipboard_restore_delay_seconds=0.4).paste("new text")

    assert pauses[-1] == 0.4
    assert consumed == ["new text"]
    assert clipboard["value"] == "old"


def test_clipboard_injector_does_not_overwrite_user_copy_during_settle_period(monkeypatch):
    import ctypes

    clipboard = {"value": "old"}

    class FakeUser32:
        def GetForegroundWindow(self):
            return 7

        def keybd_event(self, *_args):
            return None

    def sleep(seconds: float) -> None:
        if seconds == 0.4:
            clipboard["value"] = "user copied"

    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=FakeUser32()), raising=False)
    monkeypatch.setattr("src.desktop.injector.time.sleep", sleep)
    monkeypatch.setitem(
        sys.modules,
        "pyperclip",
        SimpleNamespace(paste=lambda: clipboard["value"], copy=lambda value: clipboard.update(value=value)),
    )

    ClipboardTextInjector(paste_delay_seconds=0, clipboard_restore_delay_seconds=0.4).paste("new text")

    assert clipboard["value"] == "user copied"
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
    ClipboardTextInjector(paste_delay_seconds=0, clipboard_restore_delay_seconds=0).paste("new text", target_window=7)

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
