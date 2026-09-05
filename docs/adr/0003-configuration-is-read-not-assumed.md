# ADR 0003 — Configuration is read, not assumed; stdout is the document

**Status:** accepted

## Context

`Config` declared `ANTHROPIC_MODEL`, `OPENAI_MODEL`, `LLM_TIMEOUT_SECONDS`
and `LLM_MAX_RETRIES`. The client read none of them. `generate()` hardcoded
`claude-3-5-sonnet-20240620` — a retired model, so every Anthropic call
failed regardless of `.env` — and built SDK clients with no timeout, so a hung
provider connection hung the request.

Provider errors were `print()`ed before being re-raised, and the orchestrator
`print()`ed its progress ("Running Meeting Agent...") — all to **stdout**,
where the CLI prints its JSON result. A consumer piping `python -m src.main`
into `jq` received prose mixed into the document.

## Decision

The client's default model is `Config.<PROVIDER>_MODEL`; the SDK clients are
built with `timeout` and `max_retries` from configuration. A test constructs
each client with fake SDKs and asserts the kwargs arrive.

Nothing in `src/` writes to stdout except `main()`'s final `json.dumps`.
Progress and errors go to `logging`; the CLI's own status lines go to stderr.
A test runs the orchestrator with a fake client and asserts stdout is empty.

## Consequences

Changing a model is a `.env` edit. The retired default cannot come back
unnoticed: a test walks the client module's AST and fails if the literal
appears outside a docstring.
