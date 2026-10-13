"""Tool agent with step cap, schema checks, low-score refusal, and PII redaction."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
SA_ID = re.compile(r"\b\d{13}\b")

POLICIES = [
    "Returns are accepted within 30 days if unused.",
    "Growth plan is R1499 per month and includes 10 seats.",
    "Starter has no weekend phone support.",
]

CUSTOMERS = [
    {"id": "c1", "name": "Amina Jacobs", "plan": "Growth", "city": "Cape Town"},
    {"id": "c2", "name": "Luke Meyer", "plan": "Starter", "city": "Stellenbosch"},
]


def redact(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    return SA_ID.sub("[id]", text)


def search_policy(query: str) -> dict:
    stop = {"what", "is", "the", "a", "an", "of", "to", "me", "about"}
    q = {t for t in query.lower().split() if t not in stop}
    scored = []
    for i, row in enumerate(POLICIES):
        words = set(row.lower().split())
        score = len(q & words) / max(len(q), 1)
        scored.append((score, i, row))
    scored.sort(reverse=True)
    score, i, row = scored[0]
    return {"score": round(score, 3), "doc_id": f"policy#{i}", "text": row}


def lookup_customer(plan: str) -> dict:
    rows = [c for c in CUSTOMERS if c["plan"].lower() == plan.lower()]
    return {"count": len(rows), "customers": rows}


TOOLS = {
    "search_policy": search_policy,
    "lookup_customer": lookup_customer,
}

# Exact argument shape per tool: required keys, their types, no extras.
SCHEMAS: dict[str, dict[str, type]] = {
    "search_policy": {"query": str},
    "lookup_customer": {"plan": str},
}


def check_args(name: str, args) -> str | None:
    """Return a reason string if args do not match the tool schema, else None."""
    schema = SCHEMAS[name]
    if not isinstance(args, dict):
        return "args_not_object"
    missing = sorted(set(schema) - set(args))
    extra = sorted(set(args) - set(schema))
    if missing:
        return f"missing:{','.join(missing)}"
    if extra:
        return f"unexpected:{','.join(extra)}"
    for key, typ in schema.items():
        if not isinstance(args[key], typ):
            return f"type:{key}"
    return None


@dataclass
class Trace:
    run_id: str
    steps: list[dict] = field(default_factory=list)
    status: str = "ok"
    output: str = ""

    def add(self, kind: str, **payload) -> None:
        self.steps.append({"t": round(time.time(), 3), "kind": kind, **payload})


def route(message: str) -> dict | None:
    """Deterministic stand-in for a tool-calling model. The guardrails do not trust it."""
    text = message.lower()
    if "wifi" in text or "password" in text:
        return {"tool": "search_policy", "args": {"query": message}}
    if "plan" in text or "return" in text or "support" in text or "cost" in text:
        return {"tool": "search_policy", "args": {"query": message}}
    if "customer" in text and "growth" in text:
        return {"tool": "lookup_customer", "args": {"plan": "Growth"}}
    if "customer" in text and "starter" in text:
        return {"tool": "lookup_customer", "args": {"plan": "Starter"}}
    return None


Router = Callable[[str], "dict | None"]


def run_agent(
    message: str,
    max_steps: int = 3,
    min_retrieval: float = 0.15,
    router: Router | None = None,
) -> Trace:
    """Run one request. `router` proposes a tool call; the guards below decide.

    Default router is the offline `route()`. Pass agent.llm.make_llm_router()
    for the OpenAI-compatible path. Redaction runs before any router sees text.
    """
    router = router or route
    trace = Trace(run_id=uuid.uuid4().hex[:8])
    clean = redact(message)
    if clean != message:
        # Store only the redacted text. The raw input must not land in trace files.
        trace.add("redact", after=clean, emails=len(EMAIL.findall(message)), ids=len(SA_ID.findall(message)))
    message = clean
    for step in range(max_steps):
        try:
            call = router(message)
        except Exception as exc:  # network error, bad response: fail closed
            trace.status = "router_error"
            trace.output = "Router failed. Not answering."
            trace.add("guard", reason="router_error", error=f"{type(exc).__name__}: {exc}")
            return trace
        trace.add("model", step=step, router=getattr(router, "__name__", "router"), call=call)
        if call is None:
            trace.status = "no_tool"
            trace.output = "No safe tool for that request."
            return trace
        name = call.get("tool")
        args = call.get("args")
        if name not in TOOLS:
            trace.status = "blocked_unknown_tool"
            trace.output = f"Blocked unknown tool {name}."
            trace.add("guard", reason="unknown_tool", tool=name)
            return trace
        bad = check_args(name, call.get("args"))
        if bad:
            trace.status = "blocked_schema"
            trace.output = "Blocked malformed tool arguments."
            trace.add("guard", reason="schema", detail=bad)
            return trace
        result = TOOLS[name](**args)
        trace.add("tool", tool=name, args=args, result=result)
        if name == "search_policy" and result["score"] < min_retrieval:
            trace.status = "abstain_low_score"
            trace.output = "Retrieval score too low. Not answering."
            trace.add("guard", reason="low_score", score=result["score"])
            return trace
        trace.status = "ok"
        if name == "search_policy":
            trace.output = f"{result['text']} [{result['doc_id']}]"
        else:
            trace.output = f"{result['count']} customers on that plan."
        return trace
    trace.status = "step_cap"
    trace.output = "Stopped at step cap."
    return trace


def save_trace(trace: Trace, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{trace.run_id}.json"
    path.write_text(json.dumps({"run_id": trace.run_id, "status": trace.status, "output": trace.output, "steps": trace.steps}, indent=2))
    return path
