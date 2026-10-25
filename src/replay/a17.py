"""A17 (D41): Claude Haiku 5.5 as verifier on the identical D25 contexts (cross-family; Gemini thought signatures
removed). Label: "Claude Haiku 5.5 judging in Gemini 3.1 Flash-Lite's trajectories (cross-family; Gemini thought
signatures removed)".

Design: the request is built exactly as for Flash-Lite, by the unchanged upstream request builder through
src.replay.request.run_verdict (same messages, same submit_verdict tool, upstream's 3 verdict attempts and its
no-tool-call handling). Only the backend at the single completion seam differs: `haiku_backend` converts the
upstream kwargs into an Anthropic request and sends it through LiteLLM's Anthropic route. The recorded request
(`VerdictResult.requests`) therefore stays the upstream kwargs (= the Flash-Lite request); the converted request is
attached to every response as `_a17_request` and logged in VerdictResult.extra["a17"] (hash and parameters).

Converter (`to_anthropic_messages`), exactly:
  1. Gemini thought signatures removed: in every tool-call ID and every tool message's tool_call_id, the suffix
     starting at "__thought__" is dropped; the key `provider_specific_fields` is removed from every message and
     every tool call (it holds `thought_signatures` only; checked on all items in the tests).
  2. Tool-call IDs renamed consistently (names only): characters outside [A-Za-z0-9_-] are replaced by "_"; a
     collision gets a numeric suffix; the same original ID always maps to the same new ID within a request.
  3. Empty assistant content next to tool calls (Nick-approved single exception to the A17 timebox rule, D41): an
     assistant turn with content "" and tool calls gets content None, so only its tool_use blocks are sent. Without
     it LiteLLM 1.94.1 inserts the text "[System: Empty message content sanitised to satisfy protocol]" for each
     such turn (11,800 insertions over the 400 contexts, found by the first identity test). No text is changed.
  4. Nothing else is changed: roles, order and every message text (content, tool-call names and arguments, tool
     names and results) are passed as they are. The system message stays the first message; LiteLLM's Anthropic
     transformation moves it into Anthropic's `system` field and groups consecutive tool results / user turns into
     one user turn (Anthropic's alternation rule) without changing their text (checked on the raw request in the
     tests). Messages written by Haiku itself in a later verdict attempt (no "__thought__" IDs; thinking blocks
     under `thinking_blocks`) are left as they are, so its own thinking is passed back unchanged.
Request parameters (plan 8.5, A17): model anthropic/claude-haiku-5-5; tool_choice "auto"; thinking
{"type": "adaptive"} with effort "high" (output_config.effort, sent through LiteLLM as reasoning_effort="high" for
this adaptive model; checked on the raw request); max_tokens 64,000 (the main run's output ceiling); no temperature
(Haiku 5.5 rejects sampling parameters; documented difference); tools = the upstream submit_verdict schema.
Reasoning replay: `anthropic_reasoning_replay` (scoped patch of upstream's dialect choice; see its docstring).
Stop rules (A17): any billing / credit error -> STOP file + StopA10 (no retry); 429s: upstream's retry with backoff,
STOP when more than 10 occur within 5 minutes (the A10 guard's counter); a response model other than
claude-haiku-5-5 -> STOP file, the response is returned (the call is logged), every worker stops at its next request.
Guard directory: $A10_GUARD_DIR (launcher: logs/a17_guard/<mode>/).
"""
from __future__ import annotations

import contextlib
import copy
import functools
import json
import re

from src.replay import a10
from src.replay.request import canonical_json, run_verdict, sha256_text

MODEL_HAIKU = "anthropic/claude-haiku-5-5"
SERVED_MODEL = "claude-haiku-5-5"
LABEL = ("Claude Haiku 5.5 judging in Gemini 3.1 Flash-Lite's trajectories (cross-family; Gemini thought signatures "
         "removed)")
MAX_TOKENS = 64000
THINKING = {"type": "adaptive"}
EFFORT = "high"
SIG_MARK = "__thought__"
BILLING_RE = re.compile(r"credit balance|billing|insufficient (credit|fund)|payment|spend(ing)? (cap|limit)", re.I)
ID_OK = re.compile(r"[^A-Za-z0-9_-]")


def _base_id(i: str) -> str:
    return i.split(SIG_MARK, 1)[0]


class _Renamer:
    def __init__(self):
        self.map, self.used = {}, set()

    def __call__(self, orig: str) -> str:
        if orig not in self.map:
            new = ID_OK.sub("_", _base_id(orig)) or "call"
            k, cand = 1, new
            while cand in self.used:
                k += 1
                cand = f"{new}_{k}"
            self.map[orig] = cand
            self.used.add(cand)
        return self.map[orig]


def to_anthropic_messages(messages: list) -> list:
    """The converter described in the module docstring (returns a new list; the input is not modified)."""
    ren = _Renamer()
    out = []
    for m in copy.deepcopy(messages):
        m.pop("provider_specific_fields", None)
        for tc in m.get("tool_calls") or []:
            tc.pop("provider_specific_fields", None)
            tc["id"] = ren(tc["id"])
        if m.get("role") == "tool" and m.get("tool_call_id"):
            m["tool_call_id"] = ren(m["tool_call_id"])
        if m.get("role") == "assistant" and m.get("tool_calls") and m.get("content") == "":
            m["content"] = None
        out.append(m)
    return out


def text_view(messages: list) -> list:
    """Every message text, independent of IDs and signatures: (role, content, [(tool name, arguments)], tool name).
    An empty content ("" or None) counts as no text."""
    return [(m.get("role"), m.get("content") or "",
             [(tc["function"]["name"], tc["function"]["arguments"]) for tc in m.get("tool_calls") or []],
             m.get("name")) for m in messages]


def anthropic_kwargs(kwargs: dict) -> dict:
    """The LiteLLM call for Haiku derived from the upstream (Flash-Lite) kwargs."""
    return dict(model=MODEL_HAIKU, messages=to_anthropic_messages(kwargs["messages"]), tools=kwargs.get("tools"),
                tool_choice="auto", thinking=dict(THINKING), reasoning_effort=EFFORT, max_tokens=MAX_TOKENS)


class StopA17(a10.StopA10):
    """Billing/credit error or model change (same BaseException semantics as StopA10)."""


def haiku_backend(completion=None):
    """Backend for run_verdict: converts the upstream kwargs and calls LiteLLM's Anthropic route."""
    def call(**kwargs):
        ak = anthropic_kwargs(kwargs)
        fn = completion
        if fn is None:
            import litellm
            fn = litellm.completion
        resp = fn(**ak)
        try:
            resp._a17_request = dict(sha256=sha256_text(canonical_json(ak)), n_messages=len(ak["messages"]),
                                     params={k: v for k, v in ak.items() if k not in ("messages", "tools")})
        except Exception:   # noqa: BLE001  (a mock response object may not take attributes)
            pass
        return resp
    return call


def guard_backend(backend, call: str = "", d=None):
    """A10 guard (STOP file; 429 counter; 'spending cap') plus the A17 billing and model rules."""
    d = d or a10.guard_dir()
    inner = a10.guard_backend(backend, call=call, d=d)

    def guarded(**kwargs):
        try:
            resp = inner(**kwargs)
        except a10.StopA10:
            raise
        except Exception as exc:
            text = str(exc)
            if BILLING_RE.search(text):
                a10._write_stop(d, "billing/credit error", call, text)
                raise StopA17(f"billing/credit error: {text[:300]}") from exc
            raise
        model = getattr(resp, "model", None) or ""
        if model and a10_norm(model) != SERVED_MODEL:
            a10._write_stop(d, f"response model {model!r} != {SERVED_MODEL}", call, "")
        return resp
    return guarded


def a10_norm(m: str) -> str:
    return m.split("/", 1)[1] if "/" in m else m


@contextlib.contextmanager
def anthropic_reasoning_replay():
    """While an A17 call runs, upstream's reasoning_to_replay uses its own Anthropic dialect (thinking_blocks) for
    Haiku's responses. The builder sees the Flash-Lite route, whose Gemini dialect would drop Haiku's thinking blocks
    from the stored assistant turn; with this, Haiku's thinking is kept on its own turns (logged in
    response_messages; passed back unchanged in a later verdict attempt). Context messages are not affected."""
    import experiments.agents as up_agents
    from experiments.llm import reasoning_to_replay as orig
    up_agents.reasoning_to_replay = lambda model, message: orig(MODEL_HAIKU, message)
    try:
        yield
    finally:
        up_agents.reasoning_to_replay = orig


def guarded_verdict(messages, task_type, backend, *, fn=run_verdict, **kw):
    """run_verdict with the A17 backend and guard; the converted request's hash/params go into extra["a17"]."""
    seen = []

    def recording(**kwargs):
        resp = backend(**kwargs)
        seen.append(getattr(resp, "_a17_request", None))
        return resp
    with anthropic_reasoning_replay():
        res = fn(messages, task_type, guard_backend(recording, call=kw.get("episode_id", "")), **kw)
    extra = getattr(res, "extra", None) or {}
    extra["a17"] = {"anthropic_requests": seen, "label": LABEL}
    res.extra = extra
    return res


BUILDER_MODEL = "gemini/gemini-3.1-flash-lite"   # the route the upstream builder sees: request = Flash-Lite's


def _is_runner_live_backend(backend) -> bool:
    return getattr(backend, "__qualname__", "").startswith("live_backend.")


def _mock_as_haiku(backend):
    """Mock runs only: the mock response reports the served Haiku model name, so the model rule (tested on its own)
    does not stop a mock run."""
    def call(**kw):
        resp = backend(**kw)
        try:
            resp.model = SERVED_MODEL
        except Exception:   # noqa: BLE001
            pass
        return resp
    return call


def run(messages, task_type, backend, *, judge="alice", model=None, episode_id="replay-a17"):
    """Job.verdict_fn for A17. The runner's live backend (Gemini via LiteLLM) is never used: in live mode the call goes
    to LiteLLM's Anthropic route (haiku_backend); in mock mode the runner's mock backend receives the converted kwargs.
    `model` (the job's Haiku route, used by the runner for pricing) is not passed to the builder: the builder sees the
    Flash-Lite route, so the upstream request is the Flash-Lite request."""
    del model
    be = haiku_backend() if _is_runner_live_backend(backend) else haiku_backend(completion=_mock_as_haiku(backend))
    return guarded_verdict(messages, task_type, be, judge=judge, model=BUILDER_MODEL, episode_id=episode_id)
