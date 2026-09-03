from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.agent.echo import EchoAgent


@runtime_checkable
class AgentBridge(Protocol):
    """Stable adapter contract between the API and a conversational agent."""

    def respond(self, message: str) -> str:
        """Return an agent response for one normalized user message."""


class EchoAgentBridge:
    """Default local bridge used until a real agent service is connected."""

    def __init__(self, agent: EchoAgent | None = None) -> None:
        self._agent = agent or EchoAgent()

    def respond(self, message: str) -> str:
        return self._agent.respond(message)
