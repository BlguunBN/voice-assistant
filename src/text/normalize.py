from __future__ import annotations

import re


class TextNormalizer:
    """Normalize model text without changing Mongolian words or punctuation."""

    _whitespace = re.compile(r"\s+")

    def normalize(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("TextNormalizer expects a string")
        return self._whitespace.sub(" ", text).strip()
