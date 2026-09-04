from __future__ import annotations

import ctypes
import logging
import time
from typing import Any

LOGGER = logging.getLogger(__name__)


class TextInjectionError(RuntimeError):
    """Raised when text cannot be safely pasted into the focused Windows app."""


class ClipboardTextInjector:
    """Paste text and restore the clipboard after a configurable target-app settle period."""

    def __init__(
        self,
        paste_delay_seconds: float = 0.08,
        clipboard_restore_delay_seconds: float = 0.35,
    ) -> None:
        if paste_delay_seconds < 0 or clipboard_restore_delay_seconds < 0:
            raise ValueError("Clipboard delays must not be negative")
        self.paste_delay_seconds = paste_delay_seconds
        # Keyboard paste is asynchronous in many Win32, Chromium, and Office apps.
        # Keep dictated text available while their message queues process Ctrl+V.
        self.clipboard_restore_delay_seconds = clipboard_restore_delay_seconds

    @staticmethod
    def _user32() -> Any:
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            raise TextInjectionError("Text injection requires Windows")
        return windll.user32

    def focused_window(self) -> int:
        """Return the foreground window that should receive the next paste."""
        user32 = self._user32()
        target_window = user32.GetForegroundWindow()
        if not target_window:
            raise TextInjectionError("No foreground window is available")
        return int(target_window)

    def paste(self, text: str, *, target_window: int | None = None) -> None:
        """Paste plain text into the captured target window."""
        if not text or not text.strip():
            raise TextInjectionError("Cannot inject empty text")

        import pyperclip

        user32 = self._user32()
        if target_window is None:
            target_window = self.focused_window()

        previous_text: str | None
        try:
            previous_text = pyperclip.paste()
        except (pyperclip.PyperclipException, OSError, RuntimeError):
            previous_text = None

        try:
            pyperclip.copy(text)
            time.sleep(self.paste_delay_seconds)
            if user32.GetForegroundWindow() != target_window:
                set_foreground_window = getattr(user32, "SetForegroundWindow", None)
                if set_foreground_window is None or not set_foreground_window(target_window):
                    raise TextInjectionError("The captured target window is no longer available")
                time.sleep(self.paste_delay_seconds)
            if user32.GetForegroundWindow() != target_window:
                raise TextInjectionError("The captured target window could not be focused")
            self._send_ctrl_v(user32)
            time.sleep(self.clipboard_restore_delay_seconds)
        finally:
            if previous_text is not None:
                try:
                    # Do not replace something the user copied while the target was
                    # processing the asynchronous paste.
                    if pyperclip.paste() == text:
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
