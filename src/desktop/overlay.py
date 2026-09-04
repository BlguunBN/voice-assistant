from __future__ import annotations

import ctypes
import logging
import math
import queue
import threading
import time
from pathlib import Path
from typing import Any

from src.desktop.status import DesktopStatusStore

LOGGER = logging.getLogger(__name__)


class OverlayHostError(RuntimeError):
    """Raised when the native desktop overlay cannot be started."""


class DesktopOverlayHost:
    """Small non-activating Windows dictation HUD driven by ``DesktopStatusStore``."""

    _ACTIVE_STATES = frozenset({"listening", "transcribing", "thinking", "speaking", "success", "error", "pasting"})
    _COPY = {
        "listening": "Listening", "transcribing": "Transcribing", "thinking": "Thinking",
        "speaking": "Speaking", "success": "Text pasted", "pasting": "Text pasted", "error": "Could not dictate",
    }
    _BARS = (0.34, 0.55, 0.78, 1.0, 0.68, 0.46, 0.82, 0.58, 0.36)

    def __init__(self, status_path: Path, *, width: int = 236, height: int = 64, margin: int = 18) -> None:
        if width <= 0 or height <= 0 or margin < 0:
            raise ValueError("Overlay dimensions must be positive")
        self.status_store = DesktopStatusStore(status_path)
        self.width, self.height, self.margin = width, height, margin
        self._commands: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._failure: BaseException | None = None
        self._root: Any = None
        self._canvas: Any = None
        self._visible = False
        self._state, self._detail, self._updated_at = "armed", "", 0.0
        self._phase, self._preview_until = 0.0, 0.0

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._failure = None
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="desktop-overlay", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise OverlayHostError("The native desktop overlay did not start")
        if self._failure is not None:
            raise OverlayHostError(f"The native desktop overlay could not start: {self._failure}") from self._failure

    def show(self) -> None:
        """Show a short armed preview from the tray menu without taking focus."""
        self._commands.put("show")

    def hide(self) -> None:
        self._commands.put("hide")

    def stop(self) -> None:
        if self._thread is None:
            return
        self._commands.put("stop")
        self._thread.join(timeout=3)
        if self._thread.is_alive():
            LOGGER.warning("Native desktop overlay thread did not stop cleanly")
        self._thread = None
        self._root = self._canvas = None
        self._ready.clear()

    @staticmethod
    def _enable_per_monitor_dpi() -> None:
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass

    def _run(self) -> None:
        try:
            import tkinter as tk

            self._enable_per_monitor_dpi()
            root = tk.Tk()
            self._root = root
            root.overrideredirect(True)
            root.configure(background="#000001")
            root.attributes("-topmost", True)
            try:
                root.wm_attributes("-transparentcolor", "#000001")
            except tk.TclError:
                pass
            canvas = tk.Canvas(root, width=self.width, height=self.height, highlightthickness=0, background="#000001")
            canvas.pack()
            self._canvas = canvas
            root.withdraw()
            self._apply_windows_window_flags()
            self._ready.set()
            root.after(50, self._tick)
            root.mainloop()
        except BaseException as exc:
            self._failure = exc
            self._ready.set()
            LOGGER.exception("Native desktop overlay failed")
        finally:
            self._root = self._canvas = None
            self._visible = False

    def _apply_windows_window_flags(self) -> None:
        root = self._root
        if root is None or not hasattr(ctypes, "windll"):
            return
        try:
            user32, hwnd, index = ctypes.windll.user32, root.winfo_id(), -20
            get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            set_long(hwnd, index, get_long(hwnd, index) | 0x80 | 0x08000000 | 0x20)  # toolwindow, noactivate, click-through
        except (AttributeError, OSError):
            LOGGER.debug("Could not apply optional Windows overlay flags", exc_info=True)

    def _tick(self) -> None:
        root = self._root
        if root is None:
            return
        try:
            while not self._commands.empty():
                command = self._commands.get_nowait()
                if command == "stop":
                    root.destroy()
                    return
                if command == "hide":
                    self._preview_until = 0.0
                elif command == "show":
                    self._preview_until = time.time() + 2.5
            self._sync_status()
            if self._should_show():
                self._show_at_active_monitor()
                self._render()
            elif self._visible:
                root.withdraw()
                self._visible = False
            root.after(50 if self._visible else 250, self._tick)
        except Exception as exc:
            LOGGER.warning("Native desktop overlay update failed: %s", exc)
            root.after(250, self._tick)

    def _sync_status(self) -> None:
        snapshot = self.status_store.read()
        self._state = snapshot.status if snapshot.status in self._COPY or snapshot.status in {"armed", "offline"} else "error"
        self._detail, self._updated_at = snapshot.detail or "", snapshot.updated_at

    def _should_show(self) -> bool:
        if time.time() < self._preview_until:
            return True
        if self._state not in self._ACTIVE_STATES:
            return False
        lifetime = 3.5 if self._state == "error" else 1.6 if self._state in {"success", "pasting"} else None
        return lifetime is None or time.time() - self._updated_at < lifetime

    def _show_at_active_monitor(self) -> None:
        root = self._root
        if root is None:
            return
        x, y = self._active_monitor_top_center()
        root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        if self._state in {"success", "pasting"}:
            remaining = max(0.0, 1.6 - (time.time() - self._updated_at)) / 1.6
            root.attributes("-alpha", max(0.02, 0.98 * remaining))
        else:
            root.attributes("-alpha", 0.98)
        if not self._visible:
            root.deiconify()
            self._visible = True
        try:
            ctypes.windll.user32.SetWindowPos(root.winfo_id(), -1, x, y, self.width, self.height, 0x0010 | 0x0001 | 0x0040)
        except (AttributeError, OSError):
            pass

    def _active_monitor_top_center(self) -> tuple[int, int]:
        try:
            from ctypes import wintypes

            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromWindow(user32.GetForegroundWindow(), 2)
            info = MONITORINFO(ctypes.sizeof(MONITORINFO))
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                return int(work.left + (work.right - work.left - self.width) / 2), int(work.top + self.margin)
        except (AttributeError, OSError):
            pass
        root = self._root
        return (max(0, (root.winfo_screenwidth() - self.width) // 2), self.margin) if root else (0, self.margin)

    def _render(self) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        canvas.delete("all")
        if self._state in {"success", "pasting"}:
            self._checkmark(canvas)
        elif self._state == "error":
            self._error(canvas)
        else:
            self._waveform(canvas, self._state)
        if self._state in {"error", "transcribing"}:
            label = self._detail[:40] if self._state == "error" and self._detail else self._COPY[self._state]
            canvas.create_text(self.width / 2, 49, text=label, fill="#d9d9d9", font=("Segoe UI", 9), anchor="center")

    def _pill(self, canvas: Any) -> None:
        canvas.create_oval(2, 2, 62, self.height - 2, fill="#080808", outline="#242424")
        canvas.create_oval(self.width - 62, 2, self.width - 2, self.height - 2, fill="#080808", outline="#242424")
        canvas.create_rectangle(32, 2, self.width - 32, self.height - 2, fill="#080808", outline="#080808")

    def _waveform(self, canvas: Any, state: str) -> None:
        self._pill(canvas)
        if state == "thinking":
            scales = tuple(0.4 + 0.17 * (1 + math.sin(self._phase * 0.55)) for _ in self._BARS)
        elif state == "transcribing":
            scales = tuple(0.32 + ((index + int(self._phase * 3)) % 3) * 0.13 for index in range(len(self._BARS)))
        else:
            speed = 8.0 if state in {"listening", "speaking"} else 2.0
            scales = tuple(0.42 + 0.58 * (0.5 + 0.5 * math.sin(self._phase * speed + index * 1.23)) for index in range(len(self._BARS)))
        center, gap, bar_width = self.width / 2, 6, 4
        start = center - ((len(self._BARS) - 1) * (bar_width + gap) + bar_width) / 2
        for index, (base, scale) in enumerate(zip(self._BARS, scales, strict=True)):
            height = max(4, int(31 * base * scale))
            x = start + index * (bar_width + gap)
            canvas.create_rectangle(x, 32 - height, x + bar_width, 32 + height, fill="#f4f4f4", outline="#f4f4f4")
        self._phase += 0.05

    def _checkmark(self, canvas: Any) -> None:
        self._pill(canvas)
        canvas.create_line(105, 32, 115, 42, 136, 21, fill="#f4f4f4", width=3, capstyle="round", joinstyle="round")

    def _error(self, canvas: Any) -> None:
        self._pill(canvas)
        canvas.create_oval(self.width / 2 - 10, 13, self.width / 2 + 10, 33, fill="#b94b4b", outline="")
        canvas.create_text(self.width / 2, 23, text="!", fill="#fff", font=("Segoe UI", 13, "bold"), anchor="center")
