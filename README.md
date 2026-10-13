# tool-agent-guarded

A small tool-calling loop that fails closed. The router is deterministic so the demo runs offline. The guards are the point: they do not trust the model output.

## Guards

- Redact emails and 13-digit SA ID numbers before any tool sees the text
- Reject unknown tools and bad argument shapes
- Abstain when policy retrieval score is under 0.15
- Cap steps (default 3)
- Write a JSON trace per run

## Run

```bash
pip install pytest
PYTHONPATH=. pytest -q
PYTHONPATH=. python -m agent.gallery
```

## Failure gallery

| input | status | why it stopped |
| --- | --- | --- |
| office wifi password | abstain_low_score | retrieval not confident |
| email address in the prompt | redact then answer | PII stripped before the tool |
| growth plan cost | ok | cited policy row |

Traces land in `traces/`. Open one JSON file in a review and you can see the guard that fired.

## What this is not

The router is not an LLM. Swap `route()` for a real tool-calling model and keep the same guards and trace schema. That is the production path.
