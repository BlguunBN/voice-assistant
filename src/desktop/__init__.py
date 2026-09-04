from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.audio.hotkey import HotkeyError, KeyChord
    from src.desktop.dictation import DesktopDictation, DesktopDictationError
    from src.desktop.injector import ClipboardTextInjector, TextInjectionError


__all__ = [
    "ClipboardTextInjector",
    "DesktopDictation",
    "DesktopDictationError",
    "HotkeyError",
    "KeyChord",
    "TextInjectionError",
]


def __getattr__(name: str) -> Any:
    if name in {"DesktopDictation", "DesktopDictationError"}:
        from src.desktop.dictation import DesktopDictation, DesktopDictationError

        return {"DesktopDictation": DesktopDictation, "DesktopDictationError": DesktopDictationError}[name]
    if name in {"ClipboardTextInjector", "TextInjectionError"}:
        from src.desktop.injector import ClipboardTextInjector, TextInjectionError

        return {"ClipboardTextInjector": ClipboardTextInjector, "TextInjectionError": TextInjectionError}[name]
    if name in {"HotkeyError", "KeyChord"}:
        from src.audio.hotkey import HotkeyError, KeyChord

        return {"HotkeyError": HotkeyError, "KeyChord": KeyChord}[name]
    raise AttributeError(name)
