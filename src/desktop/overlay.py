from __future__ import annotations

import logging
import queue
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from src.desktop.status import DesktopStatusStore

LOGGER = logging.getLogger(__name__)


class OverlayHostError(RuntimeError):
    """Raised when the native desktop overlay cannot be started."""


class DesktopOverlayHost:
    """Render the desktop HUD in a native, always-on-top Tk window."""

    _COPY = {
        "armed": ("VOICE ASSISTANT", "Ready when you are", "Hold Win + Alt to dictate"),
        "listening": ("CAPTURING AUDIO", "Listening", "Release Win + Alt to transcribe"),
        "transcribing": ("BILINGUAL STT", "Transcribing", "Whisper is detecting Mongolian or English"),
        "pasting": ("TEXT READY", "Inserted into your app", "Your active window has the transcript"),
        "error": ("DESKTOP COMPANION", "Needs attention", "The last dictation could not be completed"),
        "offline": ("DESKTOP COMPANION", "Overlay offline", "Start the local API and tray companion"),
    }
    _WAVEFORM = (24, 38, 18, 46, 31, 54, 26, 43, 20, 35, 48, 27, 40, 23, 51, 30, 44, 19)

    def __init__(
        self,
        status_path: Path,
        *,
        control_panel_url: str = "http://127.0.0.1:5173/",
        width: int = 400,
        height: int = 270,
        margin: int = 24,
    ) -> None:
        if width <= 0 or height <= 0 or margin < 0:
            raise ValueError("Overlay dimensions and margin must be positive")
        self.status_store = DesktopStatusStore(status_path)
        self.control_panel_url = control_panel_url
        self.width = width
        self.height = height
        self.compact_width = 248
        self.compact_height = 104
        self.margin = margin
        self._commands: queue.Queue[str] = queue.Queue()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._failure: BaseException | None = None
        self._root: Any = None
        self._canvas: Any = None
        self._expanded = False
        self._visible = False
        self._state = "offline"
        self._transcript = ""
        self._detail = ""
        self._updated_at = 0.0
        self._dismissed_at = 0.0
        self._wave_phase = 0

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self.show()
            return
        self._failure = None
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="desktop-overlay", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise OverlayHostError("The native desktop overlay did not start")
        if self._failure is not None:
            failure = self._failure
            self._thread = None
            raise OverlayHostError(f"The native desktop overlay could not start: {failure}") from failure

    def show(self) -> None:
        self._commands.put("show")

    def hide(self) -> None:
        self._commands.put("hide")

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        self._commands.put("stop")
        thread.join(timeout=3)
        if thread.is_alive():
            LOGGER.warning("Native desktop overlay thread did not stop cleanly")
        self._thread = None
        self._root = None
        self._canvas = None
        self._ready.clear()

    def _run(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            self._root = root
            root.title("Mongolian Voice Assistant")
            root.configure(background="#05080a")
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.97)
            try:
                root.wm_attributes("-transparentcolor", "#05080a")
            except tk.TclError:
                pass
            canvas = tk.Canvas(
                root,
                width=self.compact_width,
                height=self.compact_height,
                highlightthickness=0,
                background="#05080a",
            )
            canvas.pack()
            self._canvas = canvas
            canvas.bind("<Button-1>", self._on_click)
            root.bind("<Escape>", self._on_escape)
            self._set_geometry(self.compact_width, self.compact_height)
            root.deiconify()
            self._visible = True
            self._ready.set()
            root.after(100, self._tick)
            root.mainloop()
        except BaseException as exc:
            self._failure = exc
            self._ready.set()
            LOGGER.exception("Native desktop overlay failed")
        finally:
            self._root = None
            self._canvas = None
            self._visible = False

    def _tick(self) -> None:
        root = self._root
        if root is None:
            return
        try:
            while True:
                try:
                    command = self._commands.get_nowait()
                except queue.Empty:
                    break
                if command == "stop":
                    root.destroy()
                    return
                if command == "show":
                    root.deiconify()
                    root.attributes("-topmost", True)
                    self._visible = True
                elif command == "hide":
                    root.withdraw()
                    self._visible = False
            self._sync_status()
            self._render()
            root.after(120, self._tick)
        except Exception as exc:
            LOGGER.warning("Native desktop overlay update failed: %s", exc)

    def _sync_status(self) -> None:
        snapshot = self.status_store.read()
        state = snapshot.status if snapshot.status in self._COPY else "offline"
        self._state = state
        self._transcript = snapshot.transcript or ""
        self._detail = snapshot.detail or self._COPY[state][2]
        self._updated_at = snapshot.updated_at
        if state not in {"armed", "offline"} and snapshot.updated_at > self._dismissed_at:
            self._expanded = True
        elif state in {"armed", "offline"}:
            self._expanded = False
        if state == "pasting" and self._expanded and snapshot.updated_at > self._dismissed_at:
            if time.time() - snapshot.updated_at >= 2.6:
                self._dismissed_at = snapshot.updated_at
                self._expanded = False

    def _render(self) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        current_width = self.width if self._expanded else self.compact_width
        current_height = self.height if self._expanded else self.compact_height
        self._set_geometry(current_width, current_height)
        canvas.config(width=current_width, height=current_height)
        canvas.delete("all")
        accent = "#ff8f8f" if self._state in {"error", "offline"} else "#b8f36b"
        processing = self._state in {"transcribing", "pasting"}
        if processing:
            accent = "#76b6ff"
        self._rounded_panel(canvas, 5, 5, current_width - 5, current_height - 5, 20, "#11181d", accent)
        self._text(canvas, 20, 23, "▌  VA", "#dce9df", ("Segoe UI", 10, "bold"))
        self._text(canvas, current_width - 64, 23, "● LOCAL", accent, ("Consolas", 8, "bold"), anchor="e")
        if self._expanded:
            self._text(canvas, current_width - 22, 23, "−", "#96aaa1", ("Segoe UI", 14), anchor="e")

        eyebrow, title, detail = self._COPY[self._state]
        self._circle(canvas, 24, 61, 10, accent)
        self._text(canvas, 45, 52, eyebrow, "#84968e", ("Consolas", 8, "bold"))
        self._text(canvas, 45, 70, title, "#f1f7f1", ("Segoe UI", 17, "bold"))
        if not self._expanded:
            self._text(canvas, 20, current_height - 24, "HOLD TO DICTATE", "#7f9288", ("Consolas", 8, "bold"))
            self._text(canvas, current_width - 18, current_height - 24, "CONTROL PANEL ↗", accent, ("Consolas", 8, "bold"), anchor="e")
            return

        self._line(canvas, 18, 95, current_width - 18, 95, "#263237")
        self._text(canvas, 20, 113, self._detail or detail, "#b3c5bb", ("Segoe UI", 10))
        self._draw_waveform(canvas, 20, 143, current_width - 20, accent, active=self._state == "listening")
        if self._transcript:
            self._rounded_rect(canvas, 18, 164, current_width - 18, 212, 11, "#172538" if processing else "#18251d")
            self._text(canvas, 30, 178, "LAST PHRASE", "#799080", ("Consolas", 8, "bold"))
            self._text(canvas, 30, 197, self._transcript[:96], "#eff7ed", ("Segoe UI", 10))
        else:
            self._text(canvas, 20, 181, "MIC INPUT" if self._state == "listening" else "MN / EN", "#799080", ("Consolas", 8, "bold"))
            self._text(canvas, current_width - 20, 181, "LIVE" if self._state == "listening" else "STT READY", accent, ("Consolas", 8, "bold"), anchor="e")
        if self._state == "error":
            self._text(canvas, 20, 229, self._detail or "Check the tray companion and local API.", "#ffb2b2", ("Segoe UI", 9))
        self._text(canvas, 20, current_height - 20, "WIN + ALT", "#7f9288", ("Consolas", 8, "bold"))
        self._text(canvas, current_width - 18, current_height - 20, "CONTROL PANEL ↗", accent, ("Consolas", 8, "bold"), anchor="e")

    def _draw_waveform(self, canvas: Any, left: int, center: int, right: int, accent: str, *, active: bool) -> None:
        gap = 4
        bar_width = max(2, int((right - left - gap * (len(self._WAVEFORM) - 1)) / len(self._WAVEFORM)))
        for index, height in enumerate(self._WAVEFORM):
            scale = 0.62 + (0.28 * ((index + self._wave_phase) % 4) / 3) if active else 0.72
            bar_height = max(4, int(height * scale / 2))
            x = left + index * (bar_width + gap)
            self._rounded_rect(canvas, x, center - bar_height, x + bar_width, center + bar_height, 2, accent)
        if active:
            self._wave_phase = (self._wave_phase + 1) % 12

    def _on_escape(self, event: Any) -> None:
        del event
        self.hide()

    def _on_click(self, event: Any) -> None:
        if self._expanded and event.x >= self.width - 54 and event.y <= 48:
            self._dismissed_at = self._updated_at
            self._expanded = False
            return
        current_width = self.width if self._expanded else self.compact_width
        current_height = self.height if self._expanded else self.compact_height
        if event.y >= current_height - 38 and event.x >= current_width - 180:
            webbrowser.open(self.control_panel_url)

    def _set_geometry(self, width: int, height: int) -> None:
        root = self._root
        if root is None:
            return
        root.update_idletasks()
        x = max(0, root.winfo_screenwidth() - width - self.margin)
        y = max(0, root.winfo_screenheight() - height - self.margin)
        root.geometry(f"{width}x{height}+{x}+{y}")

    @staticmethod
    def _text(canvas: Any, x: int, y: int, value: str, fill: str, font: tuple[str, int, str] | tuple[str, int], *, anchor: str = "w") -> None:
        canvas.create_text(x, y, text=value, fill=fill, font=font, anchor=anchor)

    @staticmethod
    def _line(canvas: Any, x1: int, y1: int, x2: int, y2: int, fill: str) -> None:
        canvas.create_line(x1, y1, x2, y2, fill=fill)

    @staticmethod
    def _circle(canvas: Any, x: int, y: int, radius: int, fill: str) -> None:
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline=fill)

    @classmethod
    def _rounded_panel(cls, canvas: Any, x1: int, y1: int, x2: int, y2: int, radius: int, fill: str, outline: str) -> None:
        cls._rounded_rect(canvas, x1, y1, x2, y2, radius, outline)
        cls._rounded_rect(canvas, x1 + 1, y1 + 1, x2 - 1, y2 - 1, max(1, radius - 1), fill)

    @staticmethod
    def _rounded_rect(canvas: Any, x1: int, y1: int, x2: int, y2: int, radius: int, fill: str) -> None:
        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline=fill)
        canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline=fill)
        canvas.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline=fill)
        canvas.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline=fill)
        canvas.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline=fill)
        canvas.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline=fill)
