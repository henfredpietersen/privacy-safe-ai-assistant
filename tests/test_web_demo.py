"""The demo page runs agent/loop.py and web/driver.py in the browser.

These tests run the same driver under CPython and check that every example the
page offers behaves the way the page describes it, and that the built page embeds
the current code.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))

import build  # noqa: E402
import driver  # noqa: E402


def run(message, case=None):
    return json.loads(driver.demo(message, case))


def test_built_page_embeds_current_code():
    page = (ROOT / "docs" / "walkthrough.js").read_text()
    assert page == build.build(), "docs/walkthrough.js is stale: run python web/build.py"


@pytest.mark.parametrize(
    "message, status, output_starts",
    [
        ("What does the growth plan cost?", "ok", "Growth plan is R1499"),
        ("list growth customers", "ok", "1 customers"),
        ("email me at hen@example.com about returns", "ok", "Returns are accepted"),
        ("What is the office wifi password?", "abstain_low_score", "Retrieval score too low"),
        # Known failures the page labels as failures:
        ("Is there weekend phone support on the Growth plan?", "ok", "Starter has no weekend"),
        ("my ID is 8001015009087, can I return my order?", "abstain_low_score", "Retrieval score too low"),
        ("call me on 082 000 0000 about returns", "ok", "Returns are accepted"),
    ],
)
def test_page_examples_match_what_the_page_says(message, status, output_starts):
    t = run(message)
    assert t["status"] == status
    assert t["output"].startswith(output_starts)


def test_redaction_examples():
    email = json.dumps(run("email me at hen@example.com about returns"))
    assert "hen@example.com" not in email and "[email]" in email
    sa_id = json.dumps(run("my ID is 8001015009087, can I return my order?"))
    assert "8001015009087" not in sa_id and "[id]" in sa_id
    # Documented limitation: phone numbers are not redacted. If this starts failing,
    # redaction improved and the page's "known failure" copy needs updating.
    phone = json.dumps(run("call me on 082 000 0000 about returns"))
    assert "082 000 0000" in phone


@pytest.mark.parametrize(
    "case, status",
    [
        ("unknown_tool", "blocked_unknown_tool"),
        ("extra_arg", "blocked_schema"),
        ("wrong_type", "blocked_schema"),
        ("missing_arg", "blocked_schema"),
        ("bad_json", "blocked_schema"),
        ("router_timeout", "router_error"),
    ],
)
def test_misbehaving_model_is_blocked_before_any_tool(case, status):
    t = run("What does the growth plan cost?", case)
    assert t["status"] == status
    assert not any(s["kind"] == "tool" for s in t["steps"])


def test_page_lists_every_bad_case_the_driver_supports():
    page = (ROOT / "web" / "page.js").read_text()
    for case in list(driver.BAD_PROPOSALS) + ["router_timeout"]:
        assert f'c: "{case}"' in page
