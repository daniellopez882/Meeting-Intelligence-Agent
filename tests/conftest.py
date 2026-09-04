"""
Shared fixtures.

Configuration is set here rather than in a test module because
``src/core/config.py`` reads the environment at class-definition time, i.e. on
first import. Whichever test module imports it first fixes the values for the
whole session, so setting them inside one module worked in isolation and failed
in a full run.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("API_KEY", "test-api-key-not-a-real-one")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:8000")

import pytest

API_KEY = os.environ["API_KEY"]


@pytest.fixture(scope="session")
def api_key() -> str:
    return API_KEY


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from src.api import app

    with TestClient(app) as c:
        yield c
