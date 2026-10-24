"""Deterministic mock model for Study 2 dry runs (no API calls). SYNTHETIC: never a result.

It plays every phase of Shi et al.'s episode so the full upstream loop runs:
- task phase (tools include save_final_answer): save a format-valid answer ("no_bug" for code
  tasks, "[]" otherwise), then call get_log;
- communication (send_message): send "RAW LOG: <own raw log>" taken from the agent's own get_log
  result in this episode; after a "char limit" MessageError, send a short message instead. Under
  the constraint this exercises the error path, in an open channel it transmits the full log;
- verdict (submit_verdict): accept or reject, chosen from a hash of the request;
- reflection (tools sent without tool_choice, agents.run_reflection_turn): a short text.
Token usage is derived from the request size (cached share 50%) so the cost guard is exercised.
The response model is MOCK_RESPONSE_MODEL, which can never equal a live model name.
"""
from __future__ import annotations

import hashlib
import json
import os

import litellm

MOCK_RESPONSE_MODEL = "mock-study2"
REQUEST_LOG_ENV = "STUDY2_MOCK_REQUEST_LOG"   # if set: append one line per request (hash, phase)


def request_hash(kw) -> str:
    """Hash of everything the model would see: messages, tools, tool choice, sampling settings."""
    seen = {k: kw.get(k) for k in ("model", "messages", "tools", "tool_choice", "temperature", "max_tokens",
                                   "reasoning_effort")}
    return hashlib.sha256(json.dumps(seen, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _tool_names(kw) -> list[str]:
    return [t["function"]["name"] for t in kw.get("tools") or []]


def _since_last_user(messages):
    """Assistant/tool turns after the last plain user message (the current tool loop)."""
    out = []
    for m in reversed(messages):
        if m.get("role") == "user":
            break
        out.append(m)
    return list(reversed(out))


def _own_raw_log(messages):
    raw = None
    for m in messages:
        if m.get("role") == "tool" and m.get("name") == "get_log":
            try:
                raw = json.loads(m["content"])["raw_log"]
            except (ValueError, KeyError, TypeError):
                pass
    return raw


def _answer_for(kw) -> str:
    for t in kw.get("tools") or []:
        if t["function"]["name"] == "save_final_answer":
            enum = t["function"]["parameters"]["properties"]["answer"].get("enum")
            return enum[0] if enum else "[]"
    return "[]"


def _response(name, args=None, content=None, kw=None):
    n = request_hash(kw)[:16]   # deterministic in the request, so equal histories give equal runs
    prompt = max(len(json.dumps(kw.get("messages", []), ensure_ascii=False)) // 4, 1)
    msg = {"role": "assistant", "content": content}
    if name:
        msg["tool_calls"] = [{"id": f"call_mock_{n}", "type": "function",
                              "function": {"name": name, "arguments": json.dumps(args)}}]
    return litellm.ModelResponse(
        model=MOCK_RESPONSE_MODEL,
        choices=[{"index": 0, "finish_reason": "tool_calls" if name else "stop", "message": msg}],
        usage={"prompt_tokens": prompt, "completion_tokens": 40, "total_tokens": prompt + 40,
               "prompt_tokens_details": {"cached_tokens": prompt // 2}})


def mock_completion(**kw):
    if os.environ.get(REQUEST_LOG_ENV):
        with open(os.environ[REQUEST_LOG_ENV], "a") as fh:
            fh.write(json.dumps({"hash": request_hash(kw), "n_messages": len(kw.get("messages", [])),
                                 "tool_choice": kw.get("tool_choice")}, default=str) + "\n")
    names = _tool_names(kw)
    messages = kw.get("messages", [])
    digest = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).digest()
    if "tool_choice" not in kw:   # reflection: task tools are sent, no tool choice, tool calls discarded
        return _response(None, content="mock reflection", kw=kw)
    if "save_final_answer" in names:
        loop = _since_last_user(messages)
        saved = any(m.get("role") == "tool" and m.get("name") == "save_final_answer"
                    and '"success": true' in str(m.get("content")).replace("True", "true") for m in loop)
        if saved:
            return _response("get_log", {}, kw=kw)
        return _response("save_final_answer", {"reasoning": "mock reasoning", "answer": _answer_for(kw)}, kw=kw)
    if names == ["send_message"]:
        loop = _since_last_user(messages)
        limited = any(m.get("role") == "tool" and "char limit" in str(m.get("content")) for m in loop)
        raw = _own_raw_log(messages)
        text = "short mock message" if (limited or raw is None) else "RAW LOG: " + raw
        return _response("send_message", {"content": text}, kw=kw)
    if names == ["submit_verdict"]:
        verdict = "accept" if digest[0] % 10 < 7 else "reject"
        return _response("submit_verdict", {"reasoning": "mock verdict", "verdict": verdict}, kw=kw)
    raise ValueError(f"mock model: unexpected request (tools {names}, tool_choice {kw.get('tool_choice')!r})")
