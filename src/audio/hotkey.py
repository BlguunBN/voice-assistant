from __future__ import annotations

import ctypes
from dataclasses import dataclass


class HotkeyError(ValueError):
    """Raised when a Windows push-to-talk chord is invalid or unsupported."""


_VIRTUAL_KEYS = {
    "ctrl": 0x11,
    "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "space": 0x20,
}


@dataclass(frozen=True)
class KeyChord:
    """A small Windows key chord polled without installing a keyboard hook."""

    keys: tuple[str, ...]

    @classmethod
    def parse(cls, value: str) -> KeyChord:
        parts = tuple(part.strip().lower() for part in value.split("+") if part.strip())
        if not parts:
            raise HotkeyError("Push-to-talk hotkey must not be empty")
        if len(set(parts)) != len(parts):
            raise HotkeyError(f"Push-to-talk hotkey contains duplicate keys: {value!r}")
        unsupported = [part for part in parts if part not in _VIRTUAL_KEYS]
        if unsupported:
            raise HotkeyError(
                f"Unsupported push-to-talk key(s): {', '.join(unsupported)}; "
                "supported keys are ctrl, shift, alt, win, and space"
            )
        return cls(parts)

    @property
    def label(self) -> str:
        return "+".join(self.keys)

    def is_down(self) -> bool:
        """Return whether every key in the chord is currently pressed."""
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            raise HotkeyError("Push-to-talk requires Windows keyboard polling")
        return all(bool(windll.user32.GetAsyncKeyState(_VIRTUAL_KEYS[key]) & 0x8000) for key in self.keys)
