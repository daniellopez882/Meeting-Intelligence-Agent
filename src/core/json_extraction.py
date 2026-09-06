"""
src/core/json_extraction.py
Pull a JSON object out of a model response.

Each of the three agents carried its own copy of this logic, and all three had
the same four defects:

1. ``re.search(r'\\{.*\\}', text, re.DOTALL)`` is greedy: it matches from the
   first ``{`` to the last ``}``. A response like

       Sure! Here: {"a": 1}  Hope that helps {see below}

   produced ``{"a": 1}  Hope that helps {see below}``, which does not parse --
   so valid JSON that was present got reported as unparseable.

2. The fenced-block fallbacks called ``json.loads`` **outside** any try, inside
   an ``except JSONDecodeError`` handler. A malformed fenced block therefore
   raised out of the function, past the ``{"error": ...}`` fallback that looks
   like it should catch everything.

3. ``text.split("```")[1]`` raises ``IndexError`` when the response contains a
   single unmatched fence.

4. ``except:`` bare, so ``KeyboardInterrupt`` and ``SystemExit`` were caught.

This module scans for balanced braces instead of pattern-matching, tries every
candidate, and is guaranteed not to raise.
"""

from __future__ import annotations

import json
import re
from typing import Any

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _balanced_spans(text: str) -> list[tuple[int, int]]:
    """
    Byte ranges of every top-level ``{...}`` region, outermost first.

    Brace counting rather than a regex: a regex cannot match nested structures,
    and the greedy form spanned from the first brace to the last.
    """
    spans: list[tuple[int, int]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    spans.append((start, index + 1))
    return spans


def extract_json(response_text: str, *, default: dict | None = None) -> dict[str, Any]:
    """
    Return the first parseable JSON object in ``response_text``.

    Never raises. When nothing parses, returns ``default`` if given, otherwise
    ``{"error": ..., "raw_response": ...}``.

    Candidates are tried in order of how likely they are to be the intended
    payload: the whole string, then each fenced block, then each balanced
    brace region.
    """
    if not isinstance(response_text, str) or not response_text.strip():
        return (
            default
            if default is not None
            else {
                "error": "Empty response from the model",
                "raw_response": response_text,
            }
        )

    candidates: list[str] = [response_text.strip()]
    candidates.extend(block.strip() for block in FENCE.findall(response_text))
    candidates.extend(response_text[a:b] for a, b in _balanced_spans(response_text))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    if default is not None:
        return default
    return {
        "error": "Failed to parse JSON from the model response",
        "raw_response": response_text[:2000],
    }
