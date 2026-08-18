"""Governed Hermes agent driver.

Runs a *general* agent loop (Hermes-style) against any OpenAI-compatible LLM
endpoint, routing every tool call through the Enterprise-Hermes governance
stack: authenticate principal -> RBAC scope check -> tool allowlist ->
risk routing (human-approval gate for high-risk) -> execute -> immutable audit.

Provider-agnostic and egress-safe: it talks only to `LLM_BASE_URL`
(in-network by default). Uses stdlib urllib so the core has zero heavy deps.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from core.auth import Principal
from core.gates import ApprovalRequired
from core.task_queue import AgentRuntime

DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash-0731")


class LLMError(Exception):
    pass


def _chat(base_url: str, api_key: str, model: str, messages: list[dict],
          tools: list[dict] | None = None, temperature: float = 0.3,
          max_tokens: int = 1024) -> dict:
    """OpenAI-compatible chat completion via urllib (no streaming needed)."""
    url = base_url.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"LLM call failed after retries: {last_err}")


def _tool_arg_schema(tool) -> dict:
    """Permissive kwargs schema; the tool description documents the fields."""
    return {
        "type": "object",
        "properties": {},
        "description": tool.description,
        "additionalProperties": True,
    }


def _tool_specs(registry) -> list[dict]:
    specs = []
    for name in registry.allowlist():
        tool = registry.get(name)
        specs.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": f"[risk={tool.risk}] {tool.description}",
                "parameters": _tool_arg_schema(tool),
            },
        })
    return specs


def run_governed_agent(
    runtime: AgentRuntime,
    prompt: str,
    principal: Principal,
    max_iters: int = 8,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Drive a governed agent loop. Returns final answer + tool-call trace."""
    api_key = api_key or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise LLMError("LLM_API_KEY not set (set .env LLM_API_KEY / LLM_BASE_URL / LLM_MODEL)")
    base_url = base_url or DEFAULT_BASE_URL
    model = model or DEFAULT_MODEL

    sys_prompt = (
        "You are Enterprise-Hermes, a governed autonomous agent running inside a "
        "corporate firewall. You complete tasks by calling the available tools "
        "through a governance layer: RBAC, least-privilege allowlist, and "
        "human-approval gates on high-risk actions. Every call is audited. "
        "Work step by step. When you have the answer, reply with a concise final "
        "message to the user (do NOT call a tool for the final answer)."
    )
    messages: list[dict] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]
    trace: list[dict] = []
    tools = _tool_specs(runtime.registry)

    for _ in range(max_iters):
        resp = _chat(base_url, api_key, model, messages, tools=tools)
        try:
            msg = resp["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Malformed LLM response: {resp}") from exc

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            messages.append({"role": "assistant", "content": msg.get("content") or ""})
            return {"final": msg.get("content") or "", "tool_calls": trace}

        messages.append(msg)  # assistant message carrying the tool_calls
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            # --- governance routing ---
            outcome: dict = {"ok": False, "guided": "error"}
            try:
                result = runtime.execute_webreq(name, args, principal)
                outcome = {"ok": True, "result": result}
            except PermissionError as exc:
                outcome = {"ok": False, "guided": "rbac_denied", "error": str(exc)}
            except ApprovalRequired as areq:
                outcome = {
                    "ok": False,
                    "guided": "gate_required",
                    "request_id": areq.request_id,
                    "message": str(areq),
                }
            except Exception as exc:  # noqa: BLE001
                outcome = {"ok": False, "guided": "error", "error": str(exc)}

            trace.append({"tool": name, "args": args, "outcome": outcome})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "name": name,
                "content": json.dumps(outcome),
            })
    return {"final": "(no terminal answer within iteration budget)", "tool_calls": trace}