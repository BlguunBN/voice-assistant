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
            return '{"transcript":"Сайн байна уу"}'.encode()

    def fake_urlopen(request: Any, timeout: int):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(dictation_module.urllib_request, "urlopen", fake_urlopen)

    assert engine._transcribe(audio_path) == "Сайн байна уу"
    request = captured["request"]
    assert request.full_url.endswith("/stt")
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="language"' in request.data
    assert b"\r\nauto\r\n" in request.data
    assert b"dictation.wav" in request.data
    assert b"RIFF-test" in request.data


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
