"""Write the failure gallery used in the README."""

import json
from pathlib import Path

from agent.loop import run_agent, save_trace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "traces"


def main() -> None:
    cases = [
        "What does the growth plan cost?",
        "What is the office wifi password?",
        "email me at hen@example.com about returns",
        "list growth customers",
    ]
    gallery = []
    for msg in cases:
        trace = run_agent(msg)
        path = save_trace(trace, OUT)
        gallery.append({"input": msg, "status": trace.status, "output": trace.output, "file": path.name})
    (OUT / "gallery.json").write_text(json.dumps(gallery, indent=2))
    print(json.dumps(gallery, indent=2))


if __name__ == "__main__":
    main()
