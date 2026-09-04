from __future__ import annotations

import ctypes
import logging
import time
from typing import Any

LOGGER = logging.getLogger(__name__)


class TextInjectionError(RuntimeError):
    """Raised when text cannot be safely pasted into the focused Windows app."""


class ClipboardTextInjector:
    """Paste text into the foreground window while restoring text clipboard contents."""

    def __init__(self, paste_delay_seconds: float = 0.08) -> None:
        if paste_delay_seconds < 0:
            raise ValueError("paste_delay_seconds must not be negative")
        self.paste_delay_seconds = paste_delay_seconds

    @staticmethod
    def _user32() -> Any:
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            raise TextInjectionError("Text injection requires Windows")
        return windll.user32

    def paste(self, text: str) -> None:
        """Paste plain text into the window that was focused at invocation time."""
        if not text or not text.strip():
            raise TextInjectionError("Cannot inject empty text")

        import pyperclip

        user32 = self._user32()
        target_window = user32.GetForegroundWindow()
        if not target_window:
            raise TextInjectionError("No foreground window is available")

        previous_text: str | None
        try:
            previous_text = pyperclip.paste()
        except (pyperclip.PyperclipException, OSError, RuntimeError):
            previous_text = None

        try:
            pyperclip.copy(text)
            time.sleep(self.paste_delay_seconds)
            if user32.GetForegroundWindow() != target_window:
                raise TextInjectionError("Focused window changed before text injection")
            self._send_ctrl_v(user32)
            time.sleep(self.paste_delay_seconds)
        finally:
            if previous_text is not None:
                try:
                    pyperclip.copy(previous_text)
                except (pyperclip.PyperclipException, OSError, RuntimeError):
                    LOGGER.warning("Unable to restore the previous text clipboard")

    @staticmethod
    def _send_ctrl_v(user32: Any) -> None:
        key_down = 0
        key_up = 2
        user32.keybd_event(0x11, 0, key_down, 0)
        user32.keybd_event(0x56, 0, key_down, 0)
        user32.keybd_event(0x56, 0, key_up, 0)
        user32.keybd_event(0x11, 0, key_up, 0)
