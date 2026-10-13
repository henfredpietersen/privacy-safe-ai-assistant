"""Guards hold no matter which router proposes the call.

Fake routers stand in for a misbehaving model. The OpenAI response below is a
hand-written fixture in the documented chat-completions shape, not a recorded call.
"""

import json
import os

import pytest

from agent import llm
from agent.loop import TOOLS, run_agent
from agent.run import main as run_main


def _router(call):
    def r(_msg):
        return call
    return r


@pytest.fixture
def tool_spy(monkeypatch):
    calls = []
    for name, fn in list(TOOLS.items()):
        def wrapped(*a, _fn=fn, _name=name, **kw):
            calls.append(_name)
            return _fn(*a, **kw)
        monkeypatch.setitem(TOOLS, name, wrapped)
    return calls


@pytest.mark.parametrize(
    "call, status",
    [
        ({"tool": "delete_customer", "args": {"id": "c1"}}, "blocked_unknown_tool"),
        ({"tool": "search_policy", "args": {"query": "x", "limit": 99}}, "blocked_schema"),
        ({"tool": "search_policy", "args": {"query": 42}}, "blocked_schema"),
        ({"tool": "lookup_customer", "args": {}}, "blocked_schema"),
        ({"tool": "search_policy", "args": None, "raw_args": "{not json"}, "blocked_schema"),
    ],
)
def test_bad_proposals_never_reach_a_tool(call, status, tool_spy):
    trace = run_agent("anything", router=_router(call))
    assert trace.status == status
    assert tool_spy == []


def test_router_exception_fails_closed(tool_spy):
    def boom(_msg):
        raise TimeoutError("upstream slow")
    trace = run_agent("What does the growth plan cost?", router=boom)
    assert trace.status == "router_error"
    assert tool_spy == []


def test_low_score_guard_applies_to_llm_proposals():
    trace = run_agent("x", router=_router({"tool": "search_policy", "args": {"query": "office wifi password"}}))
    assert trace.status == "abstain_low_score"


def test_raw_pii_not_written_to_trace():
    trace = run_agent("my ID is 8001015009087 and email hen@example.com, returns?")
    blob = json.dumps(trace.steps)
    assert "8001015009087" not in blob
    assert "hen@example.com" not in blob


FIXTURE_RESPONSE = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search_policy", "arguments": "{\"query\": \"growth plan cost\"}"},
                    }
                ],
            }
        }
    ]
}


def test_parse_tool_call_fixture():
    assert llm.parse_tool_call(FIXTURE_RESPONSE) == {"tool": "search_policy", "args": {"query": "growth plan cost"}}
    assert llm.parse_tool_call({"choices": [{"message": {"content": "no tool"}}]}) is None
    bad = json.loads(json.dumps(FIXTURE_RESPONSE))
    bad["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{oops"
    assert llm.parse_tool_call(bad)["args"] is None


def test_llm_router_sends_redacted_text_and_tools():
    sent = {}

    def fake_post(url, headers, payload, timeout):
        sent.update(url=url, payload=payload, auth=headers["Authorization"])
        return FIXTURE_RESPONSE

    router = llm.make_llm_router(api_key="test-key", base_url="http://local/v1", model="m", http_post=fake_post)
    trace = run_agent("email hen@example.com: what does the growth plan cost?", router=router)
    assert trace.status == "ok" and "R1499" in trace.output
    assert sent["url"] == "http://local/v1/chat/completions"
    assert "hen@example.com" not in json.dumps(sent["payload"])
    assert [t["function"]["name"] for t in sent["payload"]["tools"]] == ["search_policy", "lookup_customer"]


def test_llm_path_skipped_without_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert run_main(["hi", "--router", "llm"]) == 0
    assert "skipped" in capsys.readouterr().out
    with pytest.raises(RuntimeError):
        llm.make_llm_router()


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set; live LLM path not run")
def test_live_llm_path_goes_through_guards():
    trace = run_agent("What does the growth plan cost?", router=llm.make_llm_router())
    assert trace.status in {"ok", "abstain_low_score", "no_tool", "blocked_schema", "blocked_unknown_tool"}
    assert any(s["kind"] == "model" for s in trace.steps)
