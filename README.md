# tool-agent-guarded

## Problem

A tool-calling model will sometimes propose a tool that doesn't exist, send arguments in the wrong shape, or act on weak evidence. Customer text can also contain personal data that should not reach a hosted model or a log file. This repo is a small agent loop where **the router proposes and the guards decide**. The guards do not trust the router, whether it is a rule set or an LLM.

Built AI-assisted under my direction. I specified the guards and failure cases, reviewed the output, and ran the commands shown here.

## Guards (in order)

1. **Redact** emails and 13-digit SA ID numbers before any router or tool sees the text. Traces store only the redacted text and a count of what was removed.
2. **Router call wrapped**: if it raises (timeout, bad response), status `router_error`, no tool runs.
3. **Unknown tool**: blocked.
4. **Schema check**: exact keys, correct types, no extra arguments. Malformed JSON arguments are blocked.
5. **Low retrieval score** (< 0.15) on policy search: abstain.
6. **Step cap** (default 3).
7. **JSON trace** per run, saved under `traces/`.

## Routers

- `offline` (default): deterministic keyword rules in `agent/loop.py:route()`. Not an LLM.
- `llm` (optional): `agent/llm.py`, an OpenAI-compatible `/v1/chat/completions` tool-calling request using the standard library only. It runs only when `OPENAI_API_KEY` is set. `OPENAI_BASE_URL` can point it at a self-hosted vLLM or Ollama OpenAI endpoint. Its proposals pass through the same guards.

## How to run

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q
PYTHONPATH=. python -m agent.gallery                 # rewrites traces/ and traces/gallery.json
PYTHONPATH=. python -m agent.run "What does the growth plan cost?"
cp .env.example .env   # add a key, export it, then:
PYTHONPATH=. python -m agent.run "What does the growth plan cost?" --router llm
```

Without a key, `--router llm` prints `skipped: OPENAI_API_KEY not set, LLM path not run.` and exits 0.

## Measured

`traces/gallery.json` is the output of `python -m agent.gallery` (offline router). Statuses and outputs come from real runs. The `expected` column is my note on what a correct answer would be.

| input (as logged) | status | output | expected |
| --- | --- | --- | --- |
| What does the growth plan cost? | ok | Growth plan is R1499 per month and includes 10 seats. [policy#1] | answer from policy#1 |
| What is the office wifi password? | abstain_low_score | Retrieval score too low. Not answering. | abstain |
| email me at [email] about returns | ok | Returns are accepted within 30 days if unused. [policy#0] | redact, then answer |
| list growth customers | ok | 1 customers on that plan. | 1 Growth customer |
| Is there weekend phone support on the Growth plan? | ok | Starter has no weekend phone support. [policy#2] | **FAILURE**: answers about the wrong plan, and the guards pass it |
| my ID is [id], can I return my order? | abstain_low_score | Retrieval score too low. Not answering. | **FAILURE**: answerable question refused, because lexical match misses "return" vs "Returns" |

What the two failures show:

- **Wrong-plan answer.** The score guard checks that retrieval found *something* similar. It does not check that the retrieved row answers *this* question. A real fix needs an entity check (the plan named in the question must match the plan in the cited row) or an LLM judge on the answer.
- **False refusal.** Redaction worked (the trace stores `[id]`, not the number). Retrieval is word overlap with no stemming, so "return" does not match "Returns". A real fix is embedding retrieval with a calibrated threshold (see rag-eval-service).

**LLM path: not measured.** No API key was available in this session. The live test `test_live_llm_path_goes_through_guards` was **skipped**. The LLM code is covered by tests that use a hand-written response fixture in the documented chat-completions shape and a fake HTTP function. Those tests prove the request shape, that redacted text is what gets sent, and that the guards apply. They do not prove how a real model behaves.

## Tests

`tests/test_agent.py` (original) and `tests/test_guards_llm.py`: unknown tool, extra argument, wrong type, missing argument, malformed JSON, router exception (all blocked before any tool runs); low-score guard applied to an LLM proposal; raw PII absent from traces; payload sent to the LLM is redacted; LLM path skipped cleanly with no key.

## What I would not ship

- The keyword router. It is a stand-in.
- Word-overlap policy search, and a score guard that can't tell a wrong-plan row from a right one (failure 1).
- Regex PII redaction as the only control. It covers emails and 13-digit IDs only (no phone numbers, names, or addresses) and does not validate the SA ID checksum.
- The LLM path before it has been run against a real model with a labelled set of tool-routing cases.
- Trace files on local disk with no retention policy.
