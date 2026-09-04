from __future__ import annotations

import logging
import os
from typing import Any, Callable

from src.core.config import AppConfig


LOGGER = logging.getLogger(__name__)


class NIMError(RuntimeError):
    """Raised when the hosted NVIDIA NIM agent cannot answer."""


class NvidiaNIMAgentBridge:
    """OpenAI-compatible NVIDIA NIM chat bridge with server-side credentials."""

    def __init__(self, config: AppConfig, client_factory: Callable[..., Any] | None = None) -> None:
        self.config = config
        self._client_factory = client_factory
        self._client: Any = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.config.llm_model)

    @property
    def api_key(self) -> str:
        return os.getenv(self.config.llm_api_key_env, "").strip()

    def _client_instance(self) -> Any:
        if self._client is None:
            if not self.api_key:
                raise NIMError(f"Missing {self.config.llm_api_key_env}; configure it in the server environment")
            if not self.config.llm_model:
                raise NIMError("Missing llm.model or NVIDIA_NIM_MODEL")
            factory = self._client_factory
            if factory is None:
                from openai import OpenAI

                factory = OpenAI
            self._client = factory(
                api_key=self.api_key,
                base_url=os.getenv("NVIDIA_NIM_BASE_URL", self.config.llm_base_url).strip().rstrip("/"),
                timeout=self.config.llm_timeout_seconds,
                max_retries=2,
            )
        return self._client

    def respond(self, message: str) -> str:
        if not message.strip():
            raise NIMError("Agent message must not be empty")
        try:
            completion = self._client_instance().chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": self.config.llm_system_prompt},
                    {"role": "user", "content": message.strip()},
                ],
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
            )
            content = completion.choices[0].message.content
        except NIMError:
            raise
        except Exception as exc:
            raise NIMError(f"NVIDIA NIM request failed: {exc}") from exc
        response = str(content or "").strip()
        if not response:
            raise NIMError("NVIDIA NIM returned an empty response")
        LOGGER.info("NVIDIA NIM response model=%s characters=%d", self.config.llm_model, len(response))
        return response
