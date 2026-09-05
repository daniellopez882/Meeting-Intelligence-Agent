# ADR 0001 — One JSON extractor, guaranteed not to raise

**Status:** accepted

## Context

Each of the three agents and the orchestrator carried its own copy of a
hand-rolled "pull the JSON out of the model's reply" routine. All four had the
same four defects:

1. `re.search(r'\{.*\}', text, re.DOTALL)` is greedy — it matched from the
   first `{` to the last `}`, so a reply containing two braced regions
   produced a span that did not parse, and valid JSON that *was* present was
   reported as unparseable.
2. The fenced-block fallbacks called `json.loads` **outside** any `try`,
   inside an `except JSONDecodeError` handler — a malformed fenced block raised
   straight out of a function whose whole contract was to return an error
   dict.
3. `text.split("```")[1]` raised `IndexError` on a single unmatched fence.
4. `except:` bare, so `KeyboardInterrupt` and `SystemExit` were swallowed.

## Decision

`src/core/json_extraction.py` is the only parser. It scans for balanced
braces (skipping string contents, so a `}` inside a quoted value does not end
a region), tries the whole reply, then each fenced block, then each balanced
region, and returns the first `dict` that parses. It never raises: with a
`default`, it returns that; without one, `{"error": ..., "raw_response": ...}`.

## Consequences

An agent that receives prose around its JSON, or an unmatched fence, degrades
to an error dict the orchestrator can carry into synthesis instead of taking
the whole request down. The four copies are gone; the tests for the four
defects live in one place.
