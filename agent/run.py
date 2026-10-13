"""Run one request.

python -m agent.run "What does the growth plan cost?"              # offline router
python -m agent.run "What does the growth plan cost?" --router llm # needs OPENAI_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys

from agent import llm
from agent.loop import run_agent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("message")
    p.add_argument("--router", choices=["offline", "llm"], default="offline")
    args = p.parse_args(argv)
    router = None
    if args.router == "llm":
        if not llm.available():
            print("skipped: OPENAI_API_KEY not set, LLM path not run.")
            return 0
        router = llm.make_llm_router()
    trace = run_agent(args.message, router=router)
    print(json.dumps({"status": trace.status, "output": trace.output, "steps": trace.steps}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
