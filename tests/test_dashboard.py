"""
The dashboard page.

Three things were wrong with it, all visible from the source:

* It never sent ``X-API-Key``. Once the API required one, every submission
  from the page was a 401.
* On any response without the expected fields -- including that 401 -- it
  rendered ``confidence_score || 0.98`` as "98%", ``agents_utilized ||
  ['Meeting Agent']`` as "1", and a "Synthesis Time" of
  ``total_processing_time || 4`` seconds, a field the API never produces.
  An error was displayed as a confident four-second analysis.
* Model output was written into ``innerHTML`` unescaped. A transcript that
  makes the model echo HTML runs it in the operator's browser.
"""

from __future__ import annotations

import pathlib
import re

import pytest

PAGE = (pathlib.Path(__file__).resolve().parents[1] / "public" / "index.html").read_text(
    encoding="utf-8"
)
SCRIPT = PAGE[PAGE.index("<script>") :]


class TestAuthentication:
    def test_the_key_is_sent(self):
        assert "'X-API-Key': apiKeyInput.value" in SCRIPT

    def test_there_is_a_key_field(self):
        assert 'id="api-key"' in PAGE
        assert 'type="password"' in PAGE

    def test_the_key_lives_in_session_storage_only(self):
        assert "sessionStorage" in SCRIPT
        assert "localStorage" not in SCRIPT


class TestNoFabricatedNumbers:
    @pytest.mark.parametrize(
        "fragment",
        ["|| 0.98", "|| ['Meeting Agent']", "total_processing_time", "|| 4)", "Synthesis Time"],
    )
    def test_the_old_defaults_are_gone(self, fragment):
        assert fragment not in SCRIPT

    def test_a_missing_confidence_renders_as_a_dash(self):
        assert "typeof meta.confidence_score === 'number'" in SCRIPT
        assert ": '—'" in SCRIPT

    def test_the_only_timing_shown_is_measured_in_the_browser(self):
        assert "performance.now()" in SCRIPT
        assert "Round trip (measured here)" in SCRIPT

    @pytest.mark.parametrize(
        "fragment", ["v2.4.0", "Claude 3.5 Sonnet", "DeepSeek v3", "L3-Optimized"]
    )
    def test_invented_versions_and_model_names_are_gone(self, fragment):
        assert fragment not in PAGE


class TestErrorsAreShownNotHidden:
    def test_non_ok_responses_are_rendered(self):
        assert "if (!response.ok)" in SCRIPT
        assert "function renderError" in SCRIPT

    def test_the_request_id_is_surfaced(self):
        assert "detail.request_id" in SCRIPT

    def test_no_alert(self):
        assert "alert(" not in SCRIPT


class TestOutputIsEscaped:
    def test_an_escape_helper_exists(self):
        assert "function esc(" in SCRIPT

    def test_model_fields_are_never_interpolated_raw(self):
        """The old code did `${res.executive_summary}` straight into innerHTML."""
        raw = re.findall(r"\$\{(res\.[a-z_]+|i\[[a-z]+\]|data\.[a-z_.]+)\}", SCRIPT)
        assert raw == [], f"raw interpolation of model output: {raw}"

    @pytest.mark.parametrize(
        "field", ["res.executive_summary", "sales.deal_health.overall_score", "data.error"]
    )
    def test_each_model_field_goes_through_esc(self, field):
        assert f"esc({field})" in SCRIPT

    def test_raw_json_uses_text_content(self):
        assert "rawRender.textContent" in SCRIPT
        assert "rawRender.innerText" not in SCRIPT


class TestCopy:
    @pytest.mark.parametrize(
        "fragment",
        [
            "production-ready",
            "ultimate brain",
            "enterprise operations",
            "Real-Time",
            "predictive win-probability",
            "Developed with",
        ],
    )
    def test_unsupported_claims_are_gone(self, fragment):
        assert fragment not in PAGE

    def test_provider_labels_name_the_settings_that_choose_the_model(self):
        assert "OPENAI_MODEL" in PAGE
        assert "ANTHROPIC_MODEL" in PAGE
