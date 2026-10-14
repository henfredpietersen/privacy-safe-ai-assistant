# Privacy-Safe AI Assistant

An AI helper for answering customer questions, wrapped in safety checks. The checks **remove personal information first, refuse to act when something looks wrong, and decline to answer when it is not sure**.

> *Previously named `tool-agent-guarded`.*

## In plain English

**The problem.** When an AI is allowed to use tools (look something up, list customers), it can go wrong in a few ways: ask for a tool that does not exist, send badly formed requests, or answer with weak evidence. Customer messages can also contain personal details that should not be sent to an outside AI service or saved in a log file.

**The idea.** The AI only *proposes* what to do. A set of checks, **the guards**, decide whether it is allowed. The guards never simply trust the AI, whether the "AI" is a simple set of rules or a real model. In order:

1. **Remove personal details.** Email addresses and 13-digit South African ID numbers are removed before anything else sees the message. The saved record keeps only the cleaned text and a count of what was removed.
2. **If the AI fails, do nothing.** A timeout or a bad reply stops the run before any tool is used.
3. **Block tools that do not exist.**
4. **Check the request is well formed.** The exact right fields, the right types and no extras.
5. **Decline when unsure.** If the search for an answer finds nothing close enough, it says it is not answering instead of guessing.
6. **Limit the steps.** At most 3 by default.
7. **Keep a record.** Every run saves a trace file, so it can be reviewed afterward.

**Two ways it can decide what to do**

- *Default:* a few simple keyword rules. No AI involved, and it needs no account or key.
- *Optional:* a real AI model, if you provide a key. Its suggestions pass through the same guards.

## Where things stand

- The guards work and are tested. Unknown tools, extra or missing fields, wrong types, broken requests and a failing AI are all blocked before any tool runs, and personal details never appear in the saved records.
- **Two honest failures are shown in the results**, kept visible on purpose:
  - **A wrong answer got through.** Asked about weekend phone support on the Growth plan, it answered about the Starter plan. The guards checked that *something* similar was found, not that it was the *right* row.
  - **A good question was refused.** A returns question was declined because the search matches whole words, so "return" did not match "Returns".
- **The real-AI option has not been tested with a real model.** No key was available. It is tested only against hand-written fake replies, which show the guards apply but not how a real AI behaves.
- Removing personal details only covers emails and 13-digit ID numbers, not phone numbers, names or addresses.

## Plain-English glossary

| Term | What it means here |
|---|---|
| Agent | An AI that can decide to use tools, not just chat |
| Guards | Safety checks that decide whether the AI's suggestion is allowed |
| Fails closed | When something goes wrong, it does nothing rather than carry on |
| Redaction | Removing personal details such as emails and ID numbers |
| Abstain | Choosing not to answer because it is not confident |
| Trace | A saved record of exactly what happened during one run |
| LLM | A large language model, the kind of AI behind chatbots |

---

## For developers: technical documentation

### Problem

A tool-calling model will sometimes propose a tool that doesn't exist, send arguments in the wrong shape, or act on weak evidence. Customer text can also contain personal data that should not reach a hosted model or a log file. This repo is a small agent loop where **the router proposes and the guards decide**. The guards do not trust the router, whether it is a rule set or an LLM.

Built AI-assisted under my direction. I specified the guards and failure cases, reviewed the output, and ran the commands shown here.

### Guards (in order)

1. **Redact** emails and 13-digit SA ID numbers before any router or tool sees the text. Traces store only the redacted text and a count of what was removed.
2. **Router call wrapped**: if it raises (timeout, bad response), status `router_error`, no tool runs.
3. **Unknown tool**: blocked.
4. **Schema check**: exact keys, correct types, no extra arguments. Malformed JSON arguments are blocked.
5. **Low retrieval score** (< 0.15) on policy search: abstain.
6. **Step cap** (default 3).
7. **JSON trace** per run, saved under `traces/`.

### Routers

- `offline` (default): deterministic keyword rules in `agent/loop.py:route()`. Not an LLM.
- `llm` (optional): `agent/llm.py`, an OpenAI-compatible `/v1/chat/completions` tool-calling request using the standard library only. It runs only when `OPENAI_API_KEY` is set. `OPENAI_BASE_URL` can point it at a self-hosted vLLM or Ollama OpenAI endpoint. Its proposals pass through the same guards.

### How to run

```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -q
PYTHONPATH=. python -m agent.gallery                 # rewrites traces/ and traces/gallery.json
PYTHONPATH=. python -m agent.run "What does the growth plan cost?"
cp .env.example .env   # add a key, export it, then:
PYTHONPATH=. python -m agent.run "What does the growth plan cost?" --router llm
```

Without a key, `--router llm` prints `skipped: OPENAI_API_KEY not set, LLM path not run.` and exits 0.

### Measured

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

### Tests

`tests/test_agent.py` (original) and `tests/test_guards_llm.py`: unknown tool, extra argument, wrong type, missing argument, malformed JSON, router exception (all blocked before any tool runs); low-score guard applied to an LLM proposal; raw PII absent from traces; payload sent to the LLM is redacted; LLM path skipped cleanly with no key.

### What I would not ship

- The keyword router. It is a stand-in.
- Word-overlap policy search, and a score guard that can't tell a wrong-plan row from a right one (failure 1).
- Regex PII redaction as the only control. It covers emails and 13-digit IDs only (no phone numbers, names, or addresses) and does not validate the SA ID checksum.
- The LLM path before it has been run against a real model with a labelled set of tool-routing cases.
- Trace files on local disk with no retention policy.
