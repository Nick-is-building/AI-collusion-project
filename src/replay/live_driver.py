"""R1-live driver (PROJECT_PLAN.md section 8.4, build step 6; A04 task 4; D16, D19).

From the cut, both agents continue live with Shi et al.'s protocol functions; scope (D19.7): communication
rounds 2-5, the close of the communication phase, and the verdict phase of both agents. No feedback, no
reflection. Bait versions only.

Alice (the measured judge). Her context at the cut is exactly the R1 bait context without the verdict
prompt: `build(ctx, "CUT", bob_r1_content=bait)[:-1]` (the runner job builds the full R1 list, so the
logged messages_sha256 equals R1's; D19.2 hash check). Alice's context is never changed (D19.5).

Bob. His stored message list of the episode up to and including the tool result of his round-1
send_message (the next stored message is Alice's injected round-2 message), made consistent with the bait
(plan 8.4: "his tool calls, saved answer, get_log result, and round-1 message"):
  - every task-phase tool call that corresponds to an entry of his private log (matched 1:1 in order,
    checked: same tool, arguments and result equal to the log entry) gets the bait log's arguments and
    result where they differ (resolve_records / query_database, save_final_answer);
  - the get_log tool result carries the bait raw log;
  - the round-1 send_message arguments carry the bait message (Alice's view minus the channel header),
    and its tool result's chars_sent is set to the new length.
  Every rewritten JSON string uses the serializer that reproduces the original string exactly
  (ensure_ascii True or False); the item fails closed if neither does. After the edits, the raw log read
  back from Bob's messages equals the bait raw log, and the round-1 message Alice saw equals the bait
  message (checked per item). Bob's thought signatures are kept (signature mode "keep").

Signature fallback (D19.5, fixed before any R1-live call): if the API rejects a request of Bob's with a
4xx client error (not 429), the item restarts from the cut with Bob's signatures removed from the
modified assistant turns ("strip_modified"); if that is rejected too, from all of Bob's assistant turns
of the current episode ("strip_episode"); if that is rejected too, the item is recorded as missing.
"Removed" means: the `__thought__...` suffix is cut from the tool-call IDs (and the matching
tool_call_id of the tool results) and `provider_specific_fields` is dropped from those turns. Every
attempt, its error, and the mode are recorded. Alice's context is the same in every attempt.

Protocol loop: for rounds 2..5 (0-based 1..4), in AGENT_IDS order (alice, bob), exactly upstream's
`_run_communication_phase` loop body (inject queued messages, one round instruction, upstream
`_run_agent_attempts` with the forced send_message tool, silence notice on failure); the upstream loop
itself starts at round 1 and opens the phase, so it cannot be resumed at the cut. Then upstream
`_close_communication_phase`, and the body of upstream `_run_verdict_phase` (`_open_verdict_phase` for
both, then per agent `_run_agent_attempts` with the forced submit_verdict, 3 attempts, and
`_record_forced_verdict` when none is recorded), unrolled only so that an API error can be attributed
to the agent whose request failed. Channel unconstrained (state throttled False), as in the source
condition.
"""
from __future__ import annotations

import copy
import functools
import json
from types import SimpleNamespace

import src.upstream  # noqa: F401
from experiments import episode_runner as up_runner
from experiments.models import AgentConfig, AgentRuntime, EpisodeRunConfig
from experiments.prompts.messages import (communication_round_instruction, communication_round_tag,
                                          incoming_channel_message, peer_delivery_failure_notice)
from experiments.protocol.state import (AGENT_IDS, agent_state, create_channel_state, deliver_runner_notice,
                                        peer_id, pop_incoming_messages, set_phase)
from experiments.tool_schemas import forced_tool_choice

from src.replay.request import MODEL, REQUEST_PARAMS, VerdictResult, messages_hash, patched_completion
from src.replay.traces import episode_bounds, get_log_raw, load_trace

MAX_ROUNDS = 5
SIGNATURE_MODES = ("keep", "strip_modified", "strip_episode")
NOT_MODIFIED_TOOLS = ("send_message", "submit_verdict", "get_log")


class LiveBuildError(ValueError):
    """Bob's history cannot be made consistent with the bait (item fails closed)."""


def _dumps_like(obj, original: str) -> str:
    for ea in (True, False):
        if json.dumps(json.loads(original), ensure_ascii=ea) == original:
            return json.dumps(obj, ensure_ascii=ea)
    raise LiveBuildError("original JSON string does not round-trip with json.dumps")


def _tool_result_idx(M: list, i: int, call_id: str, end: int) -> int:
    for j in range(i + 1, end):
        if M[j].get("role") == "tool" and M[j].get("tool_call_id") == call_id:
            return j
    raise LiveBuildError(f"no tool result for {call_id}")


def bob_start(trace: str, ep_index: int, bait: dict) -> tuple[list, dict]:
    """Bob's message list at the cut, consistent with the bait. Returns (messages, report)."""
    t = load_trace(trace)
    M = t["results"][ep_index]["agents"]["bob"]["messages"]
    s, e = episode_bounds(t, ep_index, "bob")
    orig_raw = get_log_raw(M, s, e)
    orig_log, bait_log = json.loads(orig_raw), json.loads(bait["bait_raw_log"])
    if len(orig_log) != len(bait_log):
        raise LiveBuildError("bait log length differs")
    calls = []   # (assistant idx, tool-call position, tool-result idx) in order
    first_send = None
    for i in range(s, e):
        for k, tc in enumerate(M[i].get("tool_calls") or []):
            name = tc["function"]["name"]
            if name == "send_message":
                if first_send is None:
                    first_send = (i, k, _tool_result_idx(M, i, tc["id"], e))
                continue
            if first_send is None and name != "submit_verdict":
                calls.append((i, k, _tool_result_idx(M, i, tc["id"], e)))
    if first_send is None:
        raise LiveBuildError("no round-1 send_message")
    cut = first_send[2] + 1
    out = copy.deepcopy(M[:cut])
    modified = set()
    logged = [c for c in calls if M[c[0]]["tool_calls"][c[1]]["function"]["name"] != "get_log"]
    if len(logged) != len(orig_log):
        raise LiveBuildError(f"{len(logged)} task-phase tool calls vs {len(orig_log)} log entries")
    for (i, k, ti), o, b in zip(logged, orig_log, bait_log):
        tc = out[i]["tool_calls"][k]
        if tc["function"]["name"] != o["tool"] or json.loads(tc["function"]["arguments"]) != o["arguments"] \
                or json.loads(out[ti]["content"]) != o["result"]:
            raise LiveBuildError(f"tool call at {i} does not match log entry {o.get('seq')}")
        if b["arguments"] != o["arguments"]:
            tc["function"]["arguments"] = _dumps_like(b["arguments"], tc["function"]["arguments"])
            modified.add(i)
        if b["result"] != o["result"]:
            out[ti]["content"] = _dumps_like(b["result"], out[ti]["content"])
            modified.add(i)
    gl = [c for c in calls if M[c[0]]["tool_calls"][c[1]]["function"]["name"] == "get_log"]
    if len(gl) != 1:
        raise LiveBuildError(f"{len(gl)} get_log calls before round 1")
    gi = gl[0][2]
    res = json.loads(out[gi]["content"])
    res["raw_log"] = bait["bait_raw_log"]
    out[gi]["content"] = _dumps_like(res, out[gi]["content"])
    modified.add(gl[0][0])
    i, k, ti = first_send
    tc = out[i]["tool_calls"][k]
    args = json.loads(tc["function"]["arguments"])
    ctx_msg = bait["bob_r1_content"]
    header = incoming_channel_message("bob", args.get("message_type", "other"), "",
                                      communication_round_tag(1, MAX_ROUNDS))
    if not ctx_msg.startswith(header):
        raise LiveBuildError("bait round-1 message lacks the channel header")
    new_content = ctx_msg[len(header):]
    args["content"] = new_content
    tc["function"]["arguments"] = _dumps_like(args, tc["function"]["arguments"])
    r = json.loads(out[ti]["content"])
    if "chars_sent" in r:
        r["chars_sent"] = len(new_content)
    out[ti]["content"] = _dumps_like(r, out[ti]["content"])
    modified.add(i)
    # checks: the log read back equals the bait log; Alice's view of the message equals the bait message
    if get_log_raw(out, s, cut) != bait["bait_raw_log"]:
        raise LiveBuildError("raw log read back from Bob's messages differs from the bait raw log")
    sent = json.loads(out[i]["tool_calls"][k]["function"]["arguments"])["content"]
    if header + sent != ctx_msg:
        raise LiveBuildError("Bob's round-1 send_message does not reproduce the bait message")
    orig_sent = json.loads(M[i]["tool_calls"][k]["function"]["arguments"])["content"]
    report = dict(bob_cut=cut, episode_start=s, modified_turns=sorted(modified),
                  orig_chars_sent=len(orig_sent), bob_start_sha256=messages_hash(out),
                  next_stored_message=str(M[cut].get("content"))[:40] if cut < len(M) else None)
    return out, report


def strip_signatures(messages: list, turns) -> list:
    out = copy.deepcopy(messages)
    renamed = {}
    for i in turns:
        m = out[i]
        for tc in m.get("tool_calls") or []:
            if "__thought__" in tc["id"]:
                new = tc["id"].split("__thought__")[0]
                renamed[tc["id"]] = new
                tc["id"] = new
        m.pop("provider_specific_fields", None)
    for m in out:
        if m.get("role") == "tool" and m.get("tool_call_id") in renamed:
            m["tool_call_id"] = renamed[m["tool_call_id"]]
    return out


def _is_client_rejection(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return 400 <= status < 500 and status != 429
    s = str(exc)
    return ("BadRequest" in type(exc).__name__ or "400" in s or "INVALID_ARGUMENT" in s) and "429" not in s


class _ActorError(Exception):
    def __init__(self, actor, exc):
        super().__init__(f"{actor}: {type(exc).__name__}: {exc}")
        self.actor, self.exc = actor, exc


def _continue(alice_msgs, bob_msgs, task_type, backend, *, verdict_prompts, model, episode_id, params):
    """Rounds 2-5, close, verdict phase. Returns (state, runtimes, usage, requests)."""
    p = {**REQUEST_PARAMS, **(params or {})}
    cfg_agent = dict(model=model, reasoning_effort=p["reasoning_effort"], temperature=p["temperature"],
                     max_output_tokens=p["max_output_tokens"])
    runtimes = {"alice": AgentRuntime("alice", AgentConfig(**cfg_agent), copy.deepcopy(alice_msgs)),
                "bob": AgentRuntime("bob", AgentConfig(**cfg_agent), copy.deepcopy(bob_msgs))}
    state = create_channel_state(episode_id, throttled=False)
    state["task_type"] = task_type
    set_phase(state, "communication")
    config = EpisodeRunConfig(throttled=False, max_rounds=MAX_ROUNDS, verbose=False)
    usage: list = []
    prepared = SimpleNamespace(task_type=task_type,
                               agents={a: SimpleNamespace(verdict_prompt=verdict_prompts[a]) for a in AGENT_IDS})
    tool_choice = forced_tool_choice(task_type, "communication")
    with patched_completion(backend) as rec:
        actor = None
        try:
            for round_index in range(1, MAX_ROUNDS):
                state["round"] = round_index
                for agent_id in AGENT_IDS:
                    actor = agent_id
                    rt = runtimes[agent_id]
                    up_runner._inject_incoming_messages(rt.messages, incoming=pop_incoming_messages(state, agent_id),
                                                        max_rounds=MAX_ROUNDS)
                    rt.messages.append({"role": "user",
                                        "content": communication_round_instruction(round_index + 1, MAX_ROUNDS)})
                    delivered = up_runner._run_agent_attempts(
                        runtime=rt, state=state, phase="communication", tool_choice=tool_choice,
                        episode_id=episode_id, round_index=round_index, reasoning_traces=[], usage_records=usage,
                        config=config)
                    if not delivered:
                        deliver_runner_notice(state, peer_id(agent_id),
                                              peer_delivery_failure_notice(peer=agent_id, round_number=round_index + 1))
            actor = None
            up_runner._close_communication_phase(state=state, runtimes=runtimes, config=config)
            # verdict phase: one agent at a time so a client error can be attributed
            set_phase(state, "verdict")
            up_runner._open_verdict_phase(prepared=prepared, runtimes=runtimes)
            vtc = forced_tool_choice(task_type, "verdict")
            for agent_id in AGENT_IDS:
                actor = agent_id
                up_runner._run_agent_attempts(runtime=runtimes[agent_id], state=state, phase="verdict",
                                              tool_choice=vtc, episode_id=episode_id, round_index=None,
                                              reasoning_traces=[], usage_records=usage, config=config)
                if not up_runner._has_verdict(state, agent_id):
                    up_runner._record_forced_verdict(state, agent_id)
        except Exception as exc:
            err = _ActorError(actor, exc)
            err.replay_usage, err.replay_requests = usage, rec.requests
            raise err from exc
    return state, runtimes, usage, rec.requests


def live_messages(runtimes: dict, starts: dict) -> list[dict]:
    """Channel messages sent live, in order: {round, from, content} (from the send_message calls)."""
    out = []
    for a in AGENT_IDS:
        rnd = None
        for m in runtimes[a].messages[starts[a]:]:
            if m.get("role") == "user" and str(m.get("content", "")).startswith("Use the send_message tool"):
                rnd = int(str(m["content"]).split("(round ")[1].split(" ")[0])
            for tc in m.get("tool_calls") or []:
                if tc["function"]["name"] == "send_message":
                    try:
                        c = json.loads(tc["function"]["arguments"]).get("content")
                    except (TypeError, ValueError):
                        c = None
                    out.append({"round": rnd, "from": a, "content": c})
    # one accepted message per agent and round: keep the last attempt's send in each (round, from)
    last = {}
    for x in out:
        last[(x["round"], x["from"])] = x
    order = {a: k for k, a in enumerate(AGENT_IDS)}
    return sorted(last.values(), key=lambda x: (x["round"] or 0, order[x["from"]]))


def run_r1live(messages: list, task_type: str, backend, *, trace: str, ep_index: int, bait: dict,
               judge: str = "alice", model: str = MODEL, episode_id: str = "r1live", params: dict | None = None
               ) -> VerdictResult:
    """Runner verdict_fn. `messages` = the R1 bait context (cut + verdict prompt)."""
    if judge != "alice":
        raise ValueError("R1-live judge is Alice")
    t = load_trace(trace)
    ep = t["results"][ep_index]["agents"]
    vps = {"alice": ep["alice"]["verdict_prompt"], "bob": ep["bob"]["verdict_prompt"]}
    alice_msgs = messages[:-1]
    if messages[-1]["content"] != vps["bob"]:
        raise LiveBuildError("Alice's verdict prompt differs from the stored prompt about Bob's task")
    bob_msgs, report = bob_start(trace, ep_index, bait)
    attempts, usage_all, req_all = [], [], []
    result = None
    for mode in SIGNATURE_MODES:
        if mode == "keep":
            bm = bob_msgs
        elif mode == "strip_modified":
            bm = strip_signatures(bob_msgs, report["modified_turns"])
        else:
            bm = strip_signatures(bob_msgs, [i for i in range(report["episode_start"], len(bob_msgs))
                                             if bob_msgs[i].get("role") == "assistant"])
        try:
            state, runtimes, usage, reqs = _continue(alice_msgs, bm, task_type, backend, verdict_prompts=vps,
                                                     model=model, episode_id=f"{episode_id}:{mode}", params=params)
        except _ActorError as err:
            usage_all += err.replay_usage
            req_all += err.replay_requests
            attempts.append(dict(mode=mode, actor=err.actor, error=f"{type(err.exc).__name__}: {str(err.exc)[:500]}"))
            if err.actor == "bob" and _is_client_rejection(err.exc):
                continue   # D19.5 fallback: next signature mode
            err.exc.replay_usage, err.exc.replay_requests = usage_all, req_all
            err.exc.r1live_attempts = attempts
            raise err.exc
        usage_all += usage
        req_all += reqs
        attempts.append(dict(mode=mode, actor=None, error=None))
        result = (mode, state, runtimes)
        break
    if result is None:
        exc = RuntimeError(f"R1-live: Bob's history rejected in every signature mode: {attempts}")
        exc.replay_usage, exc.replay_requests, exc.r1live_attempts = usage_all, req_all, attempts
        raise exc
    mode, state, runtimes = result
    subs = {a: agent_state(state, a)["verdict_submission"] for a in AGENT_IDS}
    starts = {"alice": len(alice_msgs), "bob": len(bob_msgs)}
    extra = {"r1live": dict(
        signature_mode=mode, attempts=attempts, bob=report, alice_start_sha256=messages_hash(alice_msgs),
        r1_messages_sha256=messages_hash(messages),
        bob_verdict=subs["bob"]["verdict"], bob_forced=bool(subs["bob"].get("forced")),
        bob_reasoning=subs["bob"].get("reasoning"),
        live_messages=live_messages(runtimes, starts),
        alice_messages_after=runtimes["alice"].messages[starts["alice"]:],
        bob_messages_after=runtimes["bob"].messages[starts["bob"]:])}
    a = subs["alice"]
    return VerdictResult(verdict=a["verdict"], reasoning=a.get("reasoning"), forced=bool(a.get("forced")),
                         requests=req_all, usage=usage_all, messages_after=runtimes["alice"].messages, extra=extra)


def r1live_verdict_fn(trace: str, ep_index: int, bait: dict):
    return functools.partial(run_r1live, trace=trace, ep_index=ep_index, bait=bait)
