from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Iterator


class AudioGate:
    """Prevent microphone capture while assistant audio is playing."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._speaking = False

    @property
    def listening_allowed(self) -> bool:
        with self._lock:
            return not self._speaking

    @contextmanager
    def speaking(self) -> Iterator[None]:
        with self._lock:
            if self._speaking:
                raise RuntimeError("Assistant playback is already active")
            self._speaking = True
        try:
            yield
        finally:
            with self._lock:
                self._speaking = False
