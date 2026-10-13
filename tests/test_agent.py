from pathlib import Path

from agent.loop import run_agent, save_trace

ROOT = Path(__file__).resolve().parents[1]


def test_answers_from_policy():
    trace = run_agent("What does the growth plan cost?")
    assert trace.status == "ok"
    assert "R1499" in trace.output


def test_abstains_on_unknown():
    trace = run_agent("What is the office wifi password?")
    assert trace.status == "abstain_low_score"


def test_redacts_email_before_tools():
    trace = run_agent("email me at hen@example.com about returns")
    assert any(s["kind"] == "redact" for s in trace.steps)
    blob = str(trace.steps)
    assert "hen@example.com" not in blob.split("redact", 1)[-1] or "[email]" in blob


def test_trace_file_roundtrip():
    trace = run_agent("list growth customers")
    path = save_trace(trace, ROOT / "traces")
    assert path.exists()
    assert "Growth" in path.read_text() or "customers" in path.read_text()
