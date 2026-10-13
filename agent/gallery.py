"""Write the failure gallery used in the README. Offline router only.

Every status and output in traces/gallery.json comes from running this file.
The `expected` field is a human-written note on what a correct answer would be,
so failures are visible next to what the agent actually did.
"""

import json
from pathlib import Path

from agent.loop import run_agent, save_trace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "traces"

CASES = [
    ("What does the growth plan cost?", "answer from policy#1"),
    ("What is the office wifi password?", "abstain, not in policy"),
    ("email me at hen@example.com about returns", "redact email, then answer from policy#0"),
    ("list growth customers", "1 Growth customer"),
    # Failures kept on purpose:
    ("Is there weekend phone support on the Growth plan?",
     "FAILURE: should say policy does not cover Growth weekends; agent answers about Starter and guards pass it"),
    ("my ID is 8001015009087, can I return my order?",
     "FAILURE: ID redacted correctly, but answerable question refused; lexical retrieval misses 'return' vs 'Returns'"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    gallery = []
    for msg, expected in CASES:
        trace = run_agent(msg)
        path = save_trace(trace, OUT)
        logged_input = next((s["after"] for s in trace.steps if s["kind"] == "redact"), msg)
        gallery.append(
            {"input": logged_input, "status": trace.status, "output": trace.output, "expected": expected, "file": path.name}
        )
    (OUT / "gallery.json").write_text(json.dumps(gallery, indent=2) + "\n")
    print(json.dumps(gallery, indent=2))


if __name__ == "__main__":
    main()
