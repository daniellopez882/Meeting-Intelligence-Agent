"""
API surface tests.

``/api/process`` calls a model on every request and was unauthenticated, so
anyone who could reach the port could spend the operator's API credit. It also
accepted an unbounded ``content`` field, so a single request could carry an
arbitrarily large transcript into that model call.
"""

from __future__ import annotations

import os

import pytest

from src.api import MAX_CONTENT_CHARS, MAX_REQUEST_CHARS

# Environment is configured in conftest.py, which runs before any test module
# is imported. src/core/config.py reads it at class-definition time, so setting
# it here would be too late once another module has already imported Config.
API_KEY = os.environ["API_KEY"]
VALID_BODY = {"request": "Summarise this", "content": "A short transcript."}


class TestAuthentication:
    def test_process_is_rejected_without_a_key(self, client):
        """It calls a model, so an open endpoint spends the operator's money."""
        assert client.post("/api/process", json=VALID_BODY).status_code == 401

    def test_process_is_rejected_with_a_wrong_key(self, client):
        r = client.post("/api/process", headers={"X-API-Key": "nope"}, json=VALID_BODY)
        assert r.status_code == 401

    def test_rejection_names_the_scheme(self, client):
        r = client.post("/api/process", json=VALID_BODY)
        assert r.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_the_expected_key_is_not_echoed(self, client):
        r = client.post("/api/process", headers={"X-API-Key": "nope"}, json=VALID_BODY)
        assert API_KEY not in r.text

    def test_health_needs_no_key(self, client):
        assert client.get("/health").status_code == 200

    def test_ready_needs_no_key(self, client):
        assert client.get("/ready").status_code in (200, 503)


class TestInputLimits:
    def test_oversized_content_is_rejected(self, client):
        body = {**VALID_BODY, "content": "x" * (MAX_CONTENT_CHARS + 1)}
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=body)
        assert r.status_code == 422

    def test_oversized_request_is_rejected(self, client):
        body = {**VALID_BODY, "request": "x" * (MAX_REQUEST_CHARS + 1)}
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=body)
        assert r.status_code == 422

    def test_empty_content_is_rejected(self, client):
        body = {**VALID_BODY, "content": ""}
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=body)
        assert r.status_code == 422

    def test_missing_fields_are_rejected(self, client):
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json={})
        assert r.status_code == 422

    @pytest.mark.parametrize("provider", ["nope", "gpt", "", "anthropic; drop"])
    def test_unknown_providers_are_rejected(self, client, provider):
        body = {**VALID_BODY, "provider": provider}
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=body)
        assert r.status_code == 422

    @pytest.mark.parametrize("provider", ["openai", "anthropic"])
    def test_known_providers_pass_validation(self, client, provider):
        """Should get past validation; 401/422 would mean it did not."""
        body = {**VALID_BODY, "provider": provider}
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=body)
        assert r.status_code not in (401, 422)


class TestReadiness:
    def test_ready_reports_each_check(self, client):
        checks = client.get("/ready").json()["checks"]
        assert set(checks) == {"llm_credentials", "api_key", "static_assets"}

    def test_credentials_are_required_for_readiness(self, client):
        assert client.get("/ready").json()["checks"]["llm_credentials"]["required"] is True

    def test_static_assets_are_not_required(self, client):
        assert client.get("/ready").json()["checks"]["static_assets"]["required"] is False


class TestErrorContract:
    def test_failures_do_not_leak_provider_detail(self, client, monkeypatch):
        """
        The handler returned detail=str(e). Provider exceptions carry endpoint
        URLs and sometimes key fragments.
        """
        import src.api as api

        secret = "sk-live-abcdefghijklmnop at https://api.internal.example/v1"

        def boom(_provider):
            raise RuntimeError(secret)

        monkeypatch.setattr(api, "get_client", boom)
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=VALID_BODY)
        assert r.status_code == 500
        assert "sk-live" not in r.text
        assert r.json()["detail"]["request_id"]

    def test_missing_credentials_yield_503_not_500(self, client, monkeypatch):
        import src.api as api

        def unconfigured(_provider):
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")

        monkeypatch.setattr(api, "get_client", unconfigured)
        r = client.post("/api/process", headers={"X-API-Key": API_KEY}, json=VALID_BODY)
        assert r.status_code == 503


class TestNoImportSideEffects:
    def test_importing_the_module_creates_no_directories(self):
        """os.makedirs("public") ran at import time."""
        import ast
        import pathlib

        source = (pathlib.Path(__file__).resolve().parents[1] / "src" / "api.py").read_text(
            encoding="utf-8"
        )
        module = ast.parse(source)
        top_level_calls = [
            node
            for node in module.body
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        ]
        rendered = [ast.dump(call) for call in top_level_calls]
        assert not any("makedirs" in text for text in rendered)
