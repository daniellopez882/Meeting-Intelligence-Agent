"""
src/api.py
HTTP surface for the meeting intelligence agents.

Changes over the previous revision:

* ``/api/process`` was unauthenticated and calls an LLM on every request, so
  anyone who could reach the port could spend the operator's API credit. It now
  requires ``X-API-Key``, compared in constant time.
* ``content`` was unbounded. A single request could carry an arbitrarily large
  transcript straight into a model call. Both fields are now capped.
* Errors returned ``detail=str(e)`` to the caller. Provider exceptions carry
  endpoint URLs and sometimes key fragments; the detail stays in the logs and
  the caller gets a correlation id.
* ``allow_origins=["*"]`` is replaced by a configured allowlist.
* ``os.makedirs("public")`` ran at import time, creating a directory as a side
  effect of importing the module.
* A fresh ``LLMClient`` was constructed per request; it is cached per provider.
* Adds ``/health`` and ``/ready``.
"""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from src.core.config import Config

logger = logging.getLogger("meeting_intelligence.api")

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
SUPPORTED_PROVIDERS = ("openai", "anthropic")

MAX_REQUEST_CHARS = 2_000
MAX_CONTENT_CHARS = 200_000  # roughly a 3-hour transcript


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production on the placeholder key would leave the model endpoint open.
    # Raising here makes uvicorn exit non-zero instead of serving.
    if Config.IS_PRODUCTION:
        Config.validate_production()
    logger.info("ready: environment=%s", Config.ENVIRONMENT)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Meeting Intelligence Agent API",
    description="Multi-agent analysis of meeting transcripts and sales conversations.",
    version="1.0.0",
    docs_url=None if Config.IS_PRODUCTION else "/docs",
    openapi_url=None if Config.IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ALLOW_ORIGINS
    or ([] if Config.IS_PRODUCTION else ["http://localhost:8000", "http://127.0.0.1:8000"]),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Depends(_api_key_header)) -> str:
    """Constant-time key check. Every model-calling endpoint depends on this."""
    if not api_key or not secrets.compare_digest(api_key, Config.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    return api_key


@lru_cache(maxsize=len(SUPPORTED_PROVIDERS))
def get_client(provider: str):
    """One client per provider, rather than one per request."""
    from src.core.llm_client import LLMClient

    return LLMClient(provider=provider)


class RequestBody(BaseModel):
    request: str = Field(..., min_length=1, max_length=MAX_REQUEST_CHARS)
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_CHARS)
    provider: str = "openai"

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, value: str) -> str:
        if value not in SUPPORTED_PROVIDERS:
            raise ValueError(f"provider must be one of {SUPPORTED_PROVIDERS}")
        return value


@app.get("/health", tags=["ops"])
async def health() -> dict[str, Any]:
    """Liveness. Touches no dependency."""
    return {"status": "healthy", "environment": Config.ENVIRONMENT, "version": app.version}


@app.get("/ready", tags=["ops"])
async def ready() -> JSONResponse:
    """Readiness: is this instance configured well enough to serve traffic?"""
    checks = {
        "llm_credentials": {
            "ok": bool(Config.OPENAI_API_KEY or Config.ANTHROPIC_API_KEY),
            "required": True,
        },
        "api_key": {
            "ok": not (Config.IS_PRODUCTION and Config.has_insecure_api_key()),
            "required": True,
        },
        "static_assets": {"ok": PUBLIC_DIR.is_dir(), "required": False},
    }
    is_ready = all(check["ok"] for check in checks.values() if check["required"])
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"ready": is_ready, "checks": checks},
    )


@app.post("/api/process", dependencies=[Depends(require_api_key)], tags=["agents"])
async def process_request(body: RequestBody, request: Request) -> dict[str, Any]:
    """Run a request through the orchestrator."""
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    try:
        from src.orchestrator.orchestrator import Orchestrator

        orchestrator = Orchestrator(get_client(body.provider))
        return orchestrator.process_request(body.request, body.content)
    except ValueError as exc:
        # Missing credentials and unsupported providers are operator errors.
        logger.error("configuration error [%s]: %s", correlation_id, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Provider exceptions carry endpoint URLs and sometimes key fragments.
        logger.exception("request failed [%s]", correlation_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "processing_failed",
                "message": "The request could not be processed. Quote the request id to support.",
                "request_id": correlation_id,
            },
        ) from exc


# Static assets are mounted only if the directory exists. It used to be created
# as a side effect of importing this module.
if PUBLIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")
else:
    logger.warning("public/ not found at %s; static assets are not served", PUBLIC_DIR)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
