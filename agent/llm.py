"""Optional OpenAI-compatible tool-calling router.

Off by default. Used only when OPENAI_API_KEY is set and the caller asks for it.
Works with any server that speaks the /v1/chat/completions tool-calling format
(OpenAI, or a local vLLM/Ollama endpoint via OPENAI_BASE_URL).

This module only *proposes* a tool call. Every proposal still goes through the
same guards in agent/loop.py: redaction happens before the message is sent,
and unknown tools / bad argument shapes are blocked after it comes back.
Standard library only, so the default install stays dependency-free.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search company policy text (pricing, returns, support hours).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "List customers on a plan.",
            "parameters": {
                "type": "object",
                "properties": {"plan": {"type": "string", "enum": ["Growth", "Starter"]}},
                "required": ["plan"],
                "additionalProperties": False,
            },
        },
    },
]

SYSTEM = (
    "You route support questions to tools. Call exactly one tool if one fits. "
    "If no tool fits, reply with text and no tool call."
)

HttpPost = Callable[[str, dict, dict, float], dict]


def available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _http_post(url: str, headers: dict, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL is config, not user input)
        return json.loads(resp.read())


def build_payload(message: str, model: str) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}],
        "tools": TOOL_SPECS,
        "tool_choice": "auto",
    }


def parse_tool_call(response: dict) -> dict | None:
    """Turn a chat-completions response into {"tool", "args"} or None.

    Malformed argument JSON is passed through as args=None plus raw_args, so the
    schema guard in loop.py blocks it and the trace shows what the model sent.
    """
    choice = (response.get("choices") or [{}])[0]
    calls = (choice.get("message") or {}).get("tool_calls") or []
    if not calls:
        return None
    fn = calls[0].get("function") or {}
    raw = fn.get("arguments")
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return {"tool": fn.get("name"), "args": None, "raw_args": raw}
    out = {"tool": fn.get("name"), "args": args}
    if len(calls) > 1:
        out["dropped_calls"] = len(calls) - 1
    return out


def make_llm_router(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 20.0,
    http_post: HttpPost | None = None,
) -> Callable[[str], dict | None]:
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; the LLM path is disabled.")
    base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    post = http_post or _http_post
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def llm_route(message: str) -> dict | None:
        response = post(f"{base_url}/chat/completions", headers, build_payload(message, model), timeout)
        return parse_tool_call(response)

    llm_route.__name__ = f"llm:{model}"
    return llm_route
