from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import llm as llm_module
from app.mock_llm import FakeLLM


def test_factory_returns_fake_llm_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    llm = llm_module.build_llm()

    assert isinstance(llm, FakeLLM)
    assert llm.model == "claude-opus-5"


def test_factory_returns_fake_llm_for_anthropic_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-test-model")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    llm = llm_module.build_llm()

    assert isinstance(llm, FakeLLM)
    assert llm.model == "claude-test-model"


def test_anthropic_client_maps_sdk_response(monkeypatch) -> None:
    calls: list[dict] = []
    sdk_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[
            SimpleNamespace(type="thinking", thinking="internal"),
            SimpleNamespace(type="text", text="Hello "),
            SimpleNamespace(type="text", text="world"),
        ],
        usage=SimpleNamespace(input_tokens=17, output_tokens=9),
        model="claude-resolved-model",
    )

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return sdk_response

    class FakeAnthropicClient:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-api-key"
            self.messages = FakeMessages()

    monkeypatch.setattr(llm_module, "Anthropic", FakeAnthropicClient)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-requested-model")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setenv("LLM_EFFORT", "high")
    monkeypatch.setenv("LLM_MAX_TOKENS", "321")

    llm = llm_module.build_llm()
    response = llm.generate("Test prompt")

    assert isinstance(llm, llm_module.AnthropicLLM)
    assert llm.model == "claude-requested-model"
    assert calls == [
        {
            "model": "claude-requested-model",
            "max_tokens": 321,
            "output_config": {"effort": "high"},
            "messages": [{"role": "user", "content": "Test prompt"}],
        }
    ]
    assert response.text == "Hello world"
    assert response.usage.input_tokens == 17
    assert response.usage.output_tokens == 9
    assert response.model == "claude-resolved-model"


def test_factory_returns_fake_llm_for_aibox_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "aibox")
    monkeypatch.setenv("LLM_MODEL", "aibox-test-model")
    monkeypatch.delenv("AIBOX_API_KEY", raising=False)

    llm = llm_module.build_llm()

    assert isinstance(llm, FakeLLM)
    assert llm.model == "aibox-test-model"


def test_aibox_client_maps_sdk_response(monkeypatch) -> None:
    constructor_calls: list[dict] = []
    create_calls: list[dict] = []
    sdk_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="AI Box answer"),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=23, completion_tokens=11),
        model="aibox-resolved-model",
    )

    class FakeCompletions:
        def create(self, **kwargs):
            create_calls.append(kwargs)
            return sdk_response

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeOpenAIClient:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            constructor_calls.append({"base_url": base_url, "api_key": api_key})
            self.chat = FakeChat()

    monkeypatch.setattr(llm_module, "OpenAI", FakeOpenAIClient)
    monkeypatch.setenv("LLM_PROVIDER", "aibox")
    monkeypatch.setenv("LLM_MODEL", "aibox-requested-model")
    monkeypatch.setenv("AIBOX_API_KEY", "aibox-test-api-key")
    monkeypatch.setenv("AIBOX_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("LLM_MAX_TOKENS", "456")

    llm = llm_module.build_llm()
    response = llm.generate("Test AI Box prompt")

    assert isinstance(llm, llm_module.AiboxLLM)
    assert llm.model == "aibox-requested-model"
    assert constructor_calls == [
        {
            "base_url": "https://gateway.example/v1",
            "api_key": "aibox-test-api-key",
        }
    ]
    assert create_calls == [
        {
            "model": "aibox-requested-model",
            "max_tokens": 456,
            "messages": [{"role": "user", "content": "Test AI Box prompt"}],
        }
    ]
    assert response.text == "AI Box answer"
    assert response.usage.input_tokens == 23
    assert response.usage.output_tokens == 11
    assert response.model == "aibox-resolved-model"


def test_aibox_raises_when_reasoning_model_returns_empty_content(monkeypatch) -> None:
    # deepseek-v4-* spend max_tokens on reasoning_content first: a tight budget
    # comes back with finish_reason="length" and an empty content field.
    sdk_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(content="", reasoning_content="thinking..."),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=25, completion_tokens=201),
        model="deepseek-v4-pro",
    )

    class FakeCompletions:
        def create(self, **kwargs):
            return sdk_response

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeCompletions()

    class FakeOpenAIClient:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            self.chat = FakeChat()

    monkeypatch.setattr(llm_module, "OpenAI", FakeOpenAIClient)
    monkeypatch.setenv("LLM_PROVIDER", "aibox")
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("AIBOX_API_KEY", "aibox-test-api-key")
    monkeypatch.delenv("AIBOX_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_MAX_TOKENS", "200")

    llm = llm_module.build_llm()

    with pytest.raises(RuntimeError, match="empty message"):
        llm.generate("Test AI Box prompt")
