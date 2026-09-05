"""
The provider client honours its own configuration.

``generate()`` used to hardcode ``claude-3-5-sonnet-20240620`` -- a retired
model -- while ``Config.ANTHROPIC_MODEL`` existed and was read by nothing.
``LLM_TIMEOUT_SECONDS`` and ``LLM_MAX_RETRIES`` were declared and never
applied.
"""

from __future__ import annotations

import logging
from typing import ClassVar

import pytest

from src.core import llm_client
from src.core.config import Config
from src.core.llm_client import LLMClient


class FakeSDK:
    """Records constructor kwargs and the model passed to a call."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.messages = self
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if "system" in kwargs:  # anthropic shape

            class Block:
                text = "anthropic text"

            class R:
                content: ClassVar[list] = [Block()]

            return R()

        class Msg:
            content = "openai text"

        class Choice:
            message = Msg()

        class R:
            choices: ClassVar[list] = [Choice()]

        return R()


@pytest.fixture
def fake_sdks(monkeypatch):
    built = {}

    def anthropic_ctor(**kwargs):
        built["anthropic"] = FakeSDK(**kwargs)
        return built["anthropic"]

    def openai_ctor(**kwargs):
        built["openai"] = FakeSDK(**kwargs)
        return built["openai"]

    monkeypatch.setattr(llm_client.anthropic, "Anthropic", anthropic_ctor)
    monkeypatch.setattr(llm_client.openai, "OpenAI", openai_ctor)
    monkeypatch.setattr(Config, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(Config, "OPENAI_API_KEY", "sk-test")
    return built


class TestModelComesFromConfiguration:
    def test_anthropic_uses_the_configured_model(self, fake_sdks, monkeypatch):
        monkeypatch.setattr(Config, "ANTHROPIC_MODEL", "claude-configured")
        LLMClient("anthropic").generate("sys", "user")
        assert fake_sdks["anthropic"].calls[0]["model"] == "claude-configured"

    def test_openai_uses_the_configured_model(self, fake_sdks, monkeypatch):
        monkeypatch.setattr(Config, "OPENAI_MODEL", "gpt-configured")
        LLMClient("openai").generate("sys", "user")
        assert fake_sdks["openai"].calls[0]["model"] == "gpt-configured"

    def test_an_explicit_model_still_wins(self, fake_sdks):
        LLMClient("anthropic").generate("sys", "user", model="explicit")
        assert fake_sdks["anthropic"].calls[0]["model"] == "explicit"

    def test_the_retired_model_is_not_the_default_anywhere(self):
        """
        claude-3-5-sonnet-20240620 no longer resolves. Asserted on the AST's
        non-docstring string literals: the module docstring names the old
        default in order to explain it, and must not satisfy this check.
        """
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(llm_client))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        literals = [
            n.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
        ]
        assert "claude-3-5-sonnet-20240620" not in literals
        assert Config.ANTHROPIC_MODEL != "claude-3-5-sonnet-20240620"


class TestTimeoutsAndRetriesAreApplied:
    @pytest.mark.parametrize("provider", ["anthropic", "openai"])
    def test_the_sdk_client_receives_them(self, fake_sdks, monkeypatch, provider):
        monkeypatch.setattr(Config, "LLM_TIMEOUT_SECONDS", 12.5)
        monkeypatch.setattr(Config, "LLM_MAX_RETRIES", 4)
        LLMClient(provider)
        assert fake_sdks[provider].kwargs["timeout"] == 12.5
        assert fake_sdks[provider].kwargs["max_retries"] == 4


class TestFailures:
    def test_a_provider_error_is_logged_not_printed(self, fake_sdks, capsys, caplog):
        client = LLMClient("anthropic")

        def boom(**kwargs):
            raise RuntimeError("upstream 500")

        fake_sdks["anthropic"].create = boom
        with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
            client.generate("sys", "user")
        assert capsys.readouterr().out == "", "error text reached stdout"
        assert "anthropic call failed" in caplog.text

    def test_an_unknown_provider_is_refused(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClient("nope")

    @pytest.mark.parametrize(
        "provider,setting", [("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")]
    )
    def test_a_missing_key_names_the_setting(self, monkeypatch, provider, setting):
        monkeypatch.setattr(Config, setting, None)
        with pytest.raises(ValueError, match=setting):
            LLMClient(provider)

    def test_an_empty_openai_reply_is_an_empty_string_not_none(self, fake_sdks):
        client = LLMClient("openai")  # constructs the fake SDK; patch it afterwards

        class Msg:
            content = None

        class Choice:
            message = Msg()

        class R:
            choices: ClassVar[list] = [Choice()]

        fake_sdks["openai"].create = lambda **kwargs: R()
        assert client.generate("sys", "user") == ""
