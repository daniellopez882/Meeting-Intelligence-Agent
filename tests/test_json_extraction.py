"""
Tests for src.core.json_extraction.

Four copies of this logic existed -- one per agent plus one in the
orchestrator -- and all four shared the same defects:

1. ``re.search(r'\\{.*\\}', text, re.DOTALL)`` is greedy, matching from the
   first ``{`` to the last ``}``. Valid JSON followed by prose containing a
   brace was reported as unparseable.
2. The fenced-block fallbacks called ``json.loads`` outside any try, inside an
   ``except JSONDecodeError`` handler, so a malformed fence raised straight
   past the ``{"error": ...}`` return that appears to catch everything.
3. ``text.split("```")[1]`` raises ``IndexError`` on a single unmatched fence.
4. ``except:`` bare.

Two of those four cases raised out of a function whose contract is to return an
error dict. In the orchestrator that took down the whole request.
"""

from __future__ import annotations

import pytest

from src.core.json_extraction import extract_json


class TestHappyPath:
    def test_plain_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_surrounding_whitespace(self):
        assert extract_json('\n\n  {"a": 1}  \n') == {"a": 1}

    def test_fenced_with_language_tag(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fenced_without_language_tag(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_nested_objects(self):
        assert extract_json('{"a": {"b": {"c": [1, 2]}}}') == {"a": {"b": {"c": [1, 2]}}}

    def test_preamble_before_the_fence(self):
        text = 'Certainly! Here is the analysis:\n```json\n{"ok": true}\n```\nLet me know.'
        assert extract_json(text) == {"ok": True}


class TestTheGreedyRegressions:
    def test_prose_with_braces_after_the_json(self):
        """The greedy regex spanned first { to last }, so this failed to parse."""
        assert extract_json('Sure! Here: {"a": 1}  Hope that helps {see below}') == {"a": 1}

    def test_two_objects_returns_the_first(self):
        assert extract_json('{"a": 1}\n{"b": 2}') == {"a": 1}

    def test_a_brace_inside_a_string_does_not_confuse_the_scan(self):
        assert extract_json('{"text": "a } brace in a string"}') == {
            "text": "a } brace in a string"
        }

    def test_an_escaped_quote_inside_a_string(self):
        assert extract_json('{"text": "he said \\"hi\\" }"}') == {"text": 'he said "hi" }'}


class TestNeverRaises:
    """The contract is to return an error dict. Two inputs used to raise."""

    @pytest.mark.parametrize(
        "text",
        [
            '```json\n{"a": 1\n```',  # malformed JSON in a fence
            "Here is a ``` fence with no pair",  # unmatched fence -> was IndexError
            "",
            "   ",
            "no json at all",
            "{",
            "}",
            "{'single': 'quotes'}",
            '{"unclosed": ',
            "```json\n```",
        ],
    )
    def test_unparseable_input_returns_an_error_dict(self, text):
        result = extract_json(text)
        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.parametrize("value", [None, 42, [], {}, object()])
    def test_non_string_input_does_not_raise(self, value):
        assert isinstance(extract_json(value), dict)

    def test_a_default_can_be_supplied(self):
        assert extract_json("nonsense", default={"fallback": True}) == {"fallback": True}

    def test_the_raw_response_is_included_for_debugging(self):
        assert "raw_response" in extract_json("nonsense")

    def test_a_very_long_response_is_truncated_in_the_error(self):
        result = extract_json("x" * 10_000)
        assert len(result["raw_response"]) <= 2000


class TestArrayAndScalarResponses:
    def test_a_bare_array_is_not_accepted_as_an_object(self):
        """Callers index the result by key, so a list is not a usable answer."""
        assert "error" in extract_json("[1, 2, 3]")

    def test_a_bare_scalar_is_not_accepted(self):
        assert "error" in extract_json('"just a string"')

    def test_an_object_inside_prose_after_an_array_is_found(self):
        assert extract_json('[1,2] and then {"a": 1}') == {"a": 1}


class TestAllCallersUseIt:
    """Guards against a fifth hand-rolled copy appearing."""

    def test_no_module_parses_fenced_blocks_by_hand(self):
        """
        Checked against the AST, not the text.

        A substring search matches the docstrings that *describe* the old
        parsing, which is how this guard first failed on its own explanation.
        The AST sees only what the code actually does.
        """
        import ast
        import pathlib

        src = pathlib.Path(__file__).resolve().parents[1] / "src"
        offenders = []

        for path in src.rglob("*.py"):
            if path.name == "json_extraction.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # Looking for `<something>.split("```...")`
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "split"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.startswith("```")
                ):
                    offenders.append(f"{path.name}:{node.lineno}")

        assert not offenders, f"hand-rolled fence parsing: {offenders}"

    def test_the_guard_would_catch_a_real_reintroduction(self):
        """The guard above is only useful if it actually fires."""
        import ast

        tree = ast.parse('text.split("```json")[1]')
        found = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "split"
            and n.args
            and isinstance(n.args[0], ast.Constant)
            and str(n.args[0].value).startswith("```")
        ]
        assert found, "the AST pattern no longer matches hand-rolled fence parsing"
