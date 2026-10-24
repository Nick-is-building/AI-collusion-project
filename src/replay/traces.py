"""Load Shi et al.'s trajectory traces and locate verdict-time contexts.

Trace layout (verified on the pinned dataset, see devlog/01_foundation.md):
- `trace["results"][e]` is episode e (0-based `episode_index`).
- `results[e]["agents"][name]["messages"]` is the agent's *cumulative* stored message list at the
  end of episode e; episode e's own messages start at len(results[e-1]...messages).
- `results[e]["llm_usage"]` lists one entry per API response (actor, phase, round, input_tokens,
  response_model, response_status, ...).
"""
from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONDITION = "communication__gemini-3-1-flash-lite__unconstrained"
TRACE_DIR = ROOT / "data" / "raw" / "traces" / "communication" / CONDITION
VERDICT_MARK = "verdict phase"
ROUND_INSTRUCTION = re.compile(r"Use the send_message tool")
PEER = {"alice": "bob", "bob": "alice"}


def trace_files():
    return sorted(TRACE_DIR.glob("rep*.json.gz"))


@lru_cache(maxsize=64)
def load_trace(name: str) -> dict:
    """`name` like 'rep001.json.gz'."""
    with gzip.open(TRACE_DIR / name, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def episode_bounds(trace: dict, ep_index: int, agent: str) -> tuple[int, int]:
    """[start, end) of episode `ep_index` within the agent's cumulative message list."""
    res = trace["results"]
    start = len(res[ep_index - 1]["agents"][agent]["messages"]) if ep_index > 0 else 0
    return start, len(res[ep_index]["agents"][agent]["messages"])


def get_log_raw(messages: list, start: int, end: int):
    """raw_log string returned by the agent's get_log call within messages[start:end], or None."""
    raw = None
    for m in messages[start:end]:
        if m.get("role") == "tool" and m.get("name") == "get_log":
            try:
                raw = json.loads(m["content"])["raw_log"]
            except (ValueError, KeyError, TypeError):
                pass
    return raw


@dataclass
class VerdictContext:
    """One directional verdict: `judge` judges `peer`'s task in episode `ep_index`."""
    trace: str
    run_id: str
    ep_index: int
    judge: str
    peer: str
    task_type: str
    peer_correct: bool
    verdict: str | None
    ep_start: int                 # first message of this episode in judge's list
    verdict_prompt_idx: int | None
    peer_raw_log: str | None
    peer_msg_idx: list = field(default_factory=list)   # judge-list indices of [from=peer] messages
    log_msg_idx: list = field(default_factory=list)     # those containing the complete raw log

    @property
    def evaluation_episode(self) -> int:
        return self.ep_index + 1

    def round_of(self, idx: int, trace: dict) -> int:
        msgs = trace["results"][self.ep_index]["agents"][self.judge]["messages"]
        return int(re.match(r"\[round=(\d+)/", msgs[idx]["content"]).group(1))


VERDICT_PROMPT_RULES = ("exact", "substring_v0")


def verdict_contexts(name: str, rule: str = "exact"):
    """Yield a VerdictContext for each episode and judge of one trace.

    rule="exact": the verdict prompt is the judge's user message equal to agents[peer]["verdict_prompt"].
    rule="substring_v0": the pre-sprint audit's rule (first user message of the episode containing
    "verdict phase"). It also matches channel messages that mention the verdict phase; kept only to
    reproduce the legacy 168-candidate frame (prior_work audit, plan figures, first item tables of
    commit 43518f0). Superseded by "exact" for everything downstream (docs/deviations.md D1).
    """
    if rule not in VERDICT_PROMPT_RULES:
        raise ValueError(rule)
    t = load_trace(name)
    for e, r in enumerate(t["results"]):
        for judge in ("alice", "bob"):
            peer = PEER[judge]
            J, P = r["agents"][judge], r["agents"][peer]
            js, je = episode_bounds(t, e, judge)
            ps, pe = episode_bounds(t, e, peer)
            msgs = J["messages"]
            if rule == "exact":
                vp = [i for i in range(js, je) if msgs[i]["role"] == "user"
                      and msgs[i]["content"] == P["verdict_prompt"]]
            else:
                vp = [i for i in range(js, je) if msgs[i]["role"] == "user"
                      and VERDICT_MARK in str(msgs[i]["content"])][:1]
            # agents[peer]["verdict_prompt"] is the prompt about the peer's task, shown to the judge.
            # (A substring search for "verdict phase" -- the pre-sprint audit's rule -- also matches
            # channel messages such as "See you in the verdict phase.")
            assert len(vp) <= 1, (name, e, judge)
            vpi = vp[0] if vp else None
            raw = get_log_raw(P["messages"], ps, pe)
            stop = vpi if vpi is not None else je
            tag = f"[from={peer}]"
            pidx = [i for i in range(js, stop) if msgs[i]["role"] == "user"
                    and isinstance(msgs[i]["content"], str) and tag in msgs[i]["content"]]
            lidx = [i for i in pidx if raw and raw in msgs[i]["content"]]
            yield VerdictContext(
                trace=name, run_id=t["run_id"], ep_index=e, judge=judge, peer=peer,
                task_type=r["task_type"], peer_correct=P.get("true_expected_verdict") == "pass",
                verdict=J.get("verdict"), ep_start=js, verdict_prompt_idx=vpi,
                peer_raw_log=raw, peer_msg_idx=pidx, log_msg_idx=lidx)


def verdict_usage(trace: dict, ep_index: int, judge: str) -> list:
    return [u for u in trace["results"][ep_index]["llm_usage"]
            if u.get("actor") == judge and u.get("phase") == "verdict"]
