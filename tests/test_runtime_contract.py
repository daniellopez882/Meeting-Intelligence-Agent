"""Startup refuses an unsafe production configuration; stdout is the document."""

from __future__ import annotations


class TestStartupRefusesUnsafeProduction:
    def test_production_on_the_placeholder_key_does_not_start(self, monkeypatch):
        """The endpoint calls a model; open in production means anyone can spend the credit."""
        import pytest
        from fastapi.testclient import TestClient

        from src.api import app
        from src.core.config import INSECURE_API_KEY, Config

        monkeypatch.setattr(Config, "IS_PRODUCTION", True)
        monkeypatch.setattr(Config, "API_KEY", INSECURE_API_KEY)
        with pytest.raises(ValueError, match="API_KEY"), TestClient(app):
            pass


class TestStdoutIsTheDocument:
    def test_the_orchestrator_writes_nothing_to_stdout(self, capsys):
        """It printed progress lines to stdout, where the CLI prints its JSON result."""
        from src.orchestrator.orchestrator import Orchestrator

        class FakeClient:
            def generate(self, system_prompt, user_content, temperature=0.2, **kw):
                return '{"orchestration_plan": {"agents_required": [], "execution_pattern": "sequential"}}'

        Orchestrator(FakeClient()).process_request("summarise", "text")
        assert capsys.readouterr().out == ""
