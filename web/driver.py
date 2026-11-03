"""Glue between the demo page and agent.loop.

The page runs this file and agent/loop.py unchanged in the visitor's browser
(Pyodide). tests/test_web_demo.py runs the same calls under CPython, so the page
and the tests exercise identical code.
"""

from __future__ import annotations

import json

from agent.loop import run_agent

# Bad proposals a misbehaving model could send. Same cases as tests/test_guards_llm.py.
BAD_PROPOSALS = {
    "unknown_tool": {"tool": "delete_customer", "args": {"id": "c1"}},
    "extra_arg": {"tool": "search_policy", "args": {"query": "growth plan", "limit": 99}},
    "wrong_type": {"tool": "search_policy", "args": {"query": 42}},
    "missing_arg": {"tool": "lookup_customer", "args": {}},
    # What agent/llm.py hands over when the model's argument JSON does not parse.
    "bad_json": {"tool": "search_policy", "args": None, "raw_args": "{not json"},
}


def _fixed(call: dict):
    def misbehaving_model(_message: str) -> dict:
        return call

    return misbehaving_model


def router_timeout(_message: str) -> dict:
    raise TimeoutError("model took too long to reply")


def demo(message: str, case: str | None = None) -> str:
    """Run one request and return the trace as JSON for the page to draw.

    case=None uses the repo's offline keyword router. Any other case swaps in a
    fake router that sends a bad proposal, to show the guards blocking it.
    """
    if case is None:
        router = None
    elif case == "router_timeout":
        router = router_timeout
    else:
        router = _fixed(BAD_PROPOSALS[case])
    trace = run_agent(message, router=router)
    return json.dumps(
        {"run_id": trace.run_id, "status": trace.status, "output": trace.output, "steps": trace.steps}
    )
