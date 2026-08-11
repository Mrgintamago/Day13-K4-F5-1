from __future__ import annotations

import os

try:
    from anthropic import Anthropic
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in deployed environments
    Anthropic = None  # type: ignore[assignment,misc]

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in deployed environments
    OpenAI = None  # type: ignore[assignment,misc]

from .mock_llm import FakeLLM, FakeResponse, FakeUsage


DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_AIBOX_BASE_URL = "https://api.ai-box.vn/v1"


class AnthropicLLM:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        effort: str,
        max_tokens: int,
    ) -> None:
        self.model = model
        self._effort = effort
        self._max_tokens = max_tokens
        if Anthropic is None:
            raise RuntimeError("The anthropic package is required for LLM_PROVIDER=anthropic")
        self._client = Anthropic(api_key=api_key)

    def generate(self, prompt: str) -> FakeResponse:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self._max_tokens,
            output_config={"effort": self._effort},
            messages=[{"role": "user", "content": prompt}],
        )

        if response.stop_reason == "refusal":
            stop_details = getattr(response, "stop_details", None)
            category = getattr(stop_details, "category", None) or "unknown"
            raise RuntimeError(f"Anthropic refusal (category: {category})")

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return FakeResponse(
            text=text,
            usage=FakeUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
            model=response.model,
        )


class AiboxLLM:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str,
        max_tokens: int,
    ) -> None:
        self.model = model
        self._max_tokens = max_tokens
        if OpenAI is None:
            raise RuntimeError("The openai package is required for LLM_PROVIDER=aibox")
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def generate(self, prompt: str) -> FakeResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        if not response.choices:
            raise RuntimeError("AI Box response contained no choices")

        return FakeResponse(
            text=response.choices[0].message.content or "",
            usage=FakeUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            ),
            model=response.model,
        )


def build_llm(model: str | None = None) -> FakeLLM | AnthropicLLM | AiboxLLM:
    selected_model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return FakeLLM(model=selected_model)

        effort = os.getenv("LLM_EFFORT", DEFAULT_EFFORT).strip().lower()
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        return AnthropicLLM(
            model=selected_model,
            api_key=api_key,
            effort=effort,
            max_tokens=max_tokens,
        )

    if provider == "aibox":
        api_key = os.getenv("AIBOX_API_KEY", "").strip()
        if not api_key:
            return FakeLLM(model=selected_model)

        base_url = os.getenv("AIBOX_BASE_URL", DEFAULT_AIBOX_BASE_URL).strip()
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
        return AiboxLLM(
            model=selected_model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
        )

    return FakeLLM(model=selected_model)
