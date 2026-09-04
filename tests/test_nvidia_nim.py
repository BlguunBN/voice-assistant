from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agent.nvidia_nim import NIMError, NvidiaNIMAgentBridge
from src.core.config import load_config


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" NIM answer "))])


class FakeClient:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_nim_bridge_uses_openai_compatible_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-secret")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "test-model")
    config = load_config()
    clients: list[FakeClient] = []

    def factory(**kwargs: object) -> FakeClient:
        client = FakeClient(**kwargs)
        clients.append(client)
        return client

    bridge = NvidiaNIMAgentBridge(config, client_factory=factory)

    assert bridge.configured is True
    assert bridge.respond("  Hello  ") == "NIM answer"
    assert clients[0].kwargs["api_key"] == "test-secret"
    call = clients[0].chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["messages"][-1] == {"role": "user", "content": "Hello"}
    assert call["max_tokens"] == config.llm_max_tokens


def test_nim_bridge_requires_key_and_model(monkeypatch: pytest.MonkeyPatch):
    config = load_config()
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_MODEL", raising=False)
    bridge = NvidiaNIMAgentBridge(config, client_factory=FakeClient)

    assert bridge.configured is False
    with pytest.raises(NIMError, match="Missing NVIDIA_API_KEY"):
        bridge.respond("Hello")


def test_nim_bridge_rejects_empty_completion(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-secret")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "test-model")

    class EmptyClient(FakeClient):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            self.chat.completions = SimpleNamespace(
                create=lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])
            )

    with pytest.raises(NIMError, match="empty response"):
        NvidiaNIMAgentBridge(load_config(), client_factory=EmptyClient).respond("Hello")
