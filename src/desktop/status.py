from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class DesktopStatus:
    """Snapshot shared between the tray companion and the overlay UI."""

    status: str
    transcript: str | None
    detail: str | None
    updated_at: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class DesktopStatusStore:
    """Persist small desktop-state snapshots with atomic file replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()

    def read(self) -> DesktopStatus:
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                return DesktopStatus("offline", None, None, 0.0)
            if not isinstance(payload, dict):
                return DesktopStatus("offline", None, None, 0.0)
            return DesktopStatus(
                status=self._string(payload.get("status"), "offline"),
                transcript=self._optional_string(payload.get("transcript")),
                detail=self._optional_string(payload.get("detail")),
                updated_at=self._number(payload.get("updated_at")),
            )

    def clear(self, status: str = "armed") -> DesktopStatus:
        return self.update(status, transcript=None, detail=None, preserve_transcript=False)

    def update(
        self,
        status: str,
        *,
        transcript: str | None = None,
        detail: str | None = None,
        preserve_transcript: bool = True,
    ) -> DesktopStatus:
        with self._lock:
            previous = self.read()
            snapshot = DesktopStatus(
                status=status,
                transcript=transcript if transcript is not None or not preserve_transcript else previous.transcript,
                detail=detail,
                updated_at=time.time(),
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            temporary_path.write_text(json.dumps(snapshot.as_dict(), ensure_ascii=False), encoding="utf-8")
            temporary_path.replace(self.path)
            return snapshot

    @staticmethod
    def _string(value: Any, fallback: str) -> str:
        return value if isinstance(value, str) and value else fallback

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _number(value: Any) -> float:
        return value if isinstance(value, (int, float)) else 0.0
