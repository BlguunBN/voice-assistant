from __future__ import annotations


class EchoAgent:
    """Stage 3 agent that returns the recognized Mongolian text unchanged."""

    def respond(self, transcript: str) -> str:
        response = transcript.strip()
        if not response:
            raise ValueError("EchoAgent cannot respond to an empty transcript")
        return response
