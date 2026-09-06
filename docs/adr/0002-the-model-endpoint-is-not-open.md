# ADR 0002 — The model-calling endpoint is authenticated, bounded, and closed in production by default

**Status:** accepted

## Context

`POST /api/process` calls a paid model on every request. It accepted any
caller, with no size limit on `content`, and answered failures with
`detail=str(e)` — which for provider exceptions carries endpoint URLs and
sometimes key fragments. `allow_origins=["*"]` let any page in any browser
call it. A fresh provider client was built per request, and importing the
module created a directory on disk as a side effect.

Anyone who could reach the port could spend the operator's API credit, one
unbounded transcript at a time.

## Decision

- `X-API-Key`, compared in constant time, on every model-calling route.
- `request` ≤ 2,000 characters; `content` ≤ 200,000 (roughly a three-hour
  transcript). Both validated before any model call.
- Errors return a correlation id; the detail goes to the log.
- CORS is a configured allowlist; empty in production means no browser origin.
- Startup runs `Config.validate_production()` in the FastAPI lifespan when
  `ENVIRONMENT=production`. On the placeholder key, or with no provider key,
  or with no CORS origin, it raises — uvicorn exits non-zero rather than
  serving. The container job in CI asserts exactly this.
- One client per provider, cached.
- `/health` (liveness) and `/ready` (configuration, credentials, static
  assets) exist.

## Consequences

The dashboard page must send the key. A development instance with the
placeholder key still works, and says so in `/ready`.
