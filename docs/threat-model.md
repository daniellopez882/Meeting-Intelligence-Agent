# Threat model

Scope: one FastAPI process exposing a model-calling endpoint and a static
dashboard, plus a CLI. No persistence, no multi-tenancy.

## What it holds

| Asset | Where | Why it matters |
|---|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | `.env` / environment | Billable; the endpoint spends them on every request |
| `API_KEY` | `.env`, and the operator's browser | Gates the model-calling route |
| Transcripts | request bodies, in memory only | Business conversations — the most sensitive thing that passes through |

`.env` is gitignored; CI fails if one is ever tracked or a key-shaped string
appears in the working tree; gitleaks scans full history. This repository's
history holds no credential (scanned).

## Threats

### T1 — Open model endpoint *(was open)*

`POST /api/process` accepted any caller with no size limit. Anyone reaching
the port could spend the operator's credit, one unbounded transcript at a
time.

**Controls.** `X-API-Key` in constant time; `content` ≤ 200,000 chars;
`request` ≤ 2,000; startup refuses production on the placeholder key.

**Residual.** One shared key; no per-caller quota. A holder of the key can
still spend freely.

### T2 — Provider detail in error responses *(was open)*

`detail=str(e)` returned provider exceptions — endpoint URLs, sometimes key
fragments — to the caller. Errors now carry a correlation id; the detail is
logged.

### T3 — Prompt injection through the transcript

The transcript is untrusted text placed in front of the model, and the
model's structured output is parsed with `extract_json`. An instruction
inside a transcript can shape the summary, the "decisions" or the "action
items" the system reports.

**Controls.** Output is parsed, never executed; `extract_json` cannot raise;
nothing acts on the output — it is returned to the caller. The workflow agent
*describes* automation; it does not run any.

**Residual.** A misleading summary is the whole risk, and it is not mitigated
here beyond the human reading it.

### T4 — Cross-origin abuse

`allow_origins=["*"]` with credentials. Now an explicit allowlist; production
refuses to start with none configured.

### T5 — Hung upstream

SDK clients were built without timeouts. `LLM_TIMEOUT_SECONDS` and
`LLM_MAX_RETRIES` are applied to both SDKs.

### T6 — Supply chain

Runtime dependencies are range-pinned; `pip-audit`, `bandit` and gitleaks run
in CI; the container runs as uid 10001.

## Not addressed

- No rate limiting or per-key quota.
- No audit log of requests beyond application logs.
- The dashboard keeps the key in the browser for the session.
