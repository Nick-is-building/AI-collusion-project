"""Run one replay verdict through Shi et al.'s own verdict-phase code path.

`run_verdict` calls upstream `episode_runner._run_agent_attempts` (phase "verdict",
VERDICT_ATTEMPTS = 3 model turns, forced `submit_verdict`, upstream retries/backoff in
`agents._complete_with_retries`, verdict recorded by `protocol.submissions._submit_verdict`, and
`_record_forced_verdict` when no verdict is recorded). The request kwargs are therefore built by
upstream code: tools from `get_tool_schemas`, `tool_choice` from `forced_tool_choice` /
`_select_tools_and_choice`, reasoning kwargs from `get_litellm_completion_kwargs`, and the message
transforms `model_visible_messages` -> `with_prose_split_from_tool_calls` ->
`with_prompt_cache_breakpoint`.

The only seam is `experiments.agents.completion` (the LiteLLM function upstream imported). Every
call goes through `_Recorder`, which captures the exact kwargs (and hashes them) and then forwards
to either a mock (dry runs; no network) or `litellm.completion` (live; only with explicit approval).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
from dataclasses import dataclass, field

import src.upstream  # noqa: F401
import experiments.agents as up_agents
from experiments import episode_runner as up_runner
from experiments.models import AgentConfig, AgentRuntime, EpisodeRunConfig
from experiments.protocol.state import agent_state, create_channel_state, set_phase
from experiments.tool_schemas import forced_tool_choice

MODEL = "gemini/gemini-3.1-flash-lite"
# Shi et al.'s settings as stored in every trace's run_config.llm_request_parameters
REQUEST_PARAMS = dict(temperature=1.0, max_output_tokens=64000, reasoning_effort="high")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def request_hash(kwargs: dict) -> str:
    """SHA-256 of the canonical JSON of the full completion kwargs (model, messages, tools, ...)."""
    return sha256_text(canonical_json(kwargs))


def messages_hash(messages: list) -> str:
    return sha256_text(canonical_json(messages))


class _Recorder:
    def __init__(self, backend):
        self.backend = backend
        self.requests: list[dict] = []

    def __call__(self, **kwargs):
        snap = copy.deepcopy(kwargs)
        self.requests.append(snap)
        return self.backend(**kwargs)


@contextlib.contextmanager
def patched_completion(backend):
    rec = _Recorder(backend)
    orig = up_agents.completion
    up_agents.completion = rec
    try:
        yield rec
    finally:
        up_agents.completion = orig


@dataclass
class VerdictResult:
    verdict: str | None
    reasoning: str | None
    forced: bool
    requests: list = field(default_factory=list)       # exact kwargs of every API call
    usage: list = field(default_factory=list)          # upstream usage records
    messages_after: list = field(default_factory=list)  # judge's list after the phase

    @property
    def request_hashes(self):
        return [request_hash(r) for r in self.requests]


def run_verdict(messages: list, task_type: str, backend, *, judge: str = "alice", model: str = MODEL,
                episode_id: str = "replay", params: dict | None = None) -> VerdictResult:
    """Run the verdict phase for `judge` on `messages` (which must end with the verdict prompt)."""
    p = {**REQUEST_PARAMS, **(params or {})}
    msgs = copy.deepcopy(messages)
    state = create_channel_state(episode_id, throttled=False)
    state["task_type"] = task_type
    set_phase(state, "verdict")
    runtime = AgentRuntime(judge, AgentConfig(model=model, reasoning_effort=p["reasoning_effort"],
                                              temperature=p["temperature"],
                                              max_output_tokens=p["max_output_tokens"]), msgs)
    usage: list = []
    cfg = EpisodeRunConfig(throttled=False, verbose=False)
    with patched_completion(backend) as rec:
        try:
            up_runner._run_agent_attempts(
                runtime=runtime, state=state, phase="verdict", tool_choice=forced_tool_choice(task_type, "verdict"),
                episode_id=episode_id, round_index=None, reasoning_traces=[], usage_records=usage, config=cfg)
        except Exception as exc:
            # keep upstream's usage/error records (e.g. 429 retries) for the runner's log
            exc.replay_usage, exc.replay_requests = usage, rec.requests
            raise
    if agent_state(state, judge)["verdict_submission"] is None:
        up_runner._record_forced_verdict(state, judge)
    sub = agent_state(state, judge)["verdict_submission"]
    return VerdictResult(verdict=sub["verdict"], reasoning=sub.get("reasoning"), forced=bool(sub.get("forced")),
                         requests=rec.requests, usage=usage, messages_after=msgs)


# ---------------------------------------------------------------- mock model (dry runs, tests)

def mock_backend(verdict: str = "accept", *, fail_first: int = 0, input_tokens: int = 0):
    """A LiteLLM-shaped fake: returns a submit_verdict tool call. `fail_first` responses carry no
    tool call (to exercise upstream's attempt loop). Makes no network call."""
    import litellm

    state = {"n": 0}

    def backend(**kwargs):
        state["n"] += 1
        tool_calls = None
        if state["n"] > fail_first:
            tool_calls = [{"id": f"call_mock{state['n']}", "type": "function",
                           "function": {"name": "submit_verdict",
                                        "arguments": json.dumps({"reasoning": "mock", "verdict": verdict})}}]
        return litellm.ModelResponse(
            model="mock-model",
            choices=[{"index": 0, "finish_reason": "tool_calls" if tool_calls else "stop",
                      "message": {"role": "assistant", "content": None if tool_calls else "no tool",
                                  "tool_calls": tool_calls}}],
            usage={"prompt_tokens": input_tokens, "completion_tokens": 10, "total_tokens": input_tokens + 10})

    return backend
