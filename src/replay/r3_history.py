"""R3t and R3o: decomposition of the earlier-episode history (D38, assignment A15).

Both start from R3 (src.replay.variants.build(ctx, "R3"): the cut context with every earlier episode's communication
phase removed). Each earlier episode k (0 <= k < ep_index) splits at the existing boundaries into
  task phase  [episode start, communication opening)
  communication [communication opening, verdict prompt)      -> already removed in R3
  outcome     [verdict prompt, episode end): verdict prompt, submit_verdict call and result, "Episode k complete"
              feedback (reward, verdict review), reflection prompt and reflection.
  R3t ("earlier work only")      removes every earlier outcome segment;
  R3o ("earlier outcomes only")  removes every earlier task phase.
The system prompt and the current episode (task phase, communication opening, Alice's round-1 message, Bob's round-1
message, verdict prompt) are kept. Kept messages are the same deep copies as in R3 (byte-identical, incl. thought
signatures); only whole segments are removed, and no tool call is separated from its result (checked by
`split_problems`, which `build` asserts).
"""
from __future__ import annotations

import copy

from src.replay.variants import ItemContext, _bob_msg

VARIANTS = ("R3t", "R3o")


def segments(ctx: ItemContext, k: int) -> dict[str, tuple[int, int]]:
    s, e = ctx.episode_slice(k)
    co, vp = ctx.comm_opening_idx(k), ctx.verdict_prompt_of(k)
    return {"task": (s, co), "comm": (co, vp), "outcome": (vp, e)}


def split_problems(ctx: ItemContext) -> list[str]:
    """Empty if every earlier episode splits cleanly into task / communication / outcome segments."""
    m, probs = ctx.messages, []
    for k in range(ctx.ep_index):
        seg = segments(ctx, k)
        s, co = seg["task"]
        vp, e = seg["outcome"]
        if not s < co < vp < e:
            probs.append(f"ep{k}: segment order")
        if not str(m[s].get("content")).startswith(f"## Episode {k + 1}: task phase"):
            probs.append(f"ep{k}: task phase start")
        if not any(str(x.get("content")).startswith(f"Episode {k + 1} complete") for x in m[vp:e]):
            probs.append(f"ep{k}: no feedback in outcome segment")
        for name, (a, b) in seg.items():
            calls = {t["id"] for x in m[a:b] for t in (x.get("tool_calls") or [])}
            results = {x["tool_call_id"] for x in m[a:b] if x["role"] == "tool"}
            if calls != results:
                probs.append(f"ep{k}: tool calls split in {name}")
    return probs


def removed_indices(ctx: ItemContext, variant: str) -> set[int]:
    """Indices into ctx.messages removed relative to the cut context (R3's removals plus the variant's)."""
    if variant not in VARIANTS:
        raise ValueError(variant)
    drop = set()
    for k in range(ctx.ep_index):
        seg = segments(ctx, k)
        drop.update(range(*seg["comm"]))
        drop.update(range(*(seg["outcome"] if variant == "R3t" else seg["task"])))
    return drop


def build(ctx: ItemContext, variant: str, bob_r1_content: str | None = None) -> list[dict]:
    probs = split_problems(ctx)
    if probs:
        raise ValueError(f"{ctx.trace} ep{ctx.ep_index}: cannot split: {probs}")
    msgs = ctx.messages
    cut = copy.deepcopy(msgs[:ctx.cut_idx]) + [_bob_msg(ctx, bob_r1_content)]
    drop = removed_indices(ctx, variant)
    return [m for i, m in enumerate(cut) if i not in drop] + [copy.deepcopy(msgs[ctx.verdict_prompt_idx])]


# ------------------------------------------------------------------ context and residual-information table (D38.2-3)

RESIDUAL_TASK_WORDS = ("extract", "record", "query", "source", "answer")
RESIDUAL_OUTCOME_WORDS = ("reward", "verdict", "accept", "reject")


def _text(msgs) -> str:
    return "\n".join(str(m.get("content") or "") for m in msgs)


def residual(ctx: ItemContext) -> dict:
    """Deterministic residual-information counts over the earlier episodes (descriptive, D38.3).
    R3o keeps the outcome segments: count those whose text names a task ID ("Your task: ..."/"Bob's task: ...")
    or mentions Bob, the log, or a task-content word. R3t keeps the task phases: count those whose text contains
    an outcome word."""
    import re
    m = ctx.messages
    out = dict(earlier_episodes=ctx.ep_index, r3o_outcome_names_task_id=0, r3o_outcome_mentions_bob=0,
               r3o_outcome_mentions_log=0, r3o_outcome_mentions_task_words=0, r3t_task_mentions_outcome_words=0)
    for k in range(ctx.ep_index):
        seg = segments(ctx, k)
        o = _text(m[slice(*seg["outcome"])])
        lo = o.lower()
        out["r3o_outcome_names_task_id"] += bool(re.search(r"(Your|Bob's) task: \S", o))
        out["r3o_outcome_mentions_bob"] += "bob" in lo
        out["r3o_outcome_mentions_log"] += bool(re.search(r"\blogs?\b|raw_log", lo))
        out["r3o_outcome_mentions_task_words"] += any(w in lo for w in RESIDUAL_TASK_WORDS)
        t = _text(m[slice(*seg["task"])]).lower()
        out["r3t_task_mentions_outcome_words"] += any(re.search(rf"\b{w}", t) for w in RESIDUAL_OUTCOME_WORDS)
    return out


def context_table(items: list[dict]) -> "pd.DataFrame":
    """Per item, variant (R1, R2, R3, R3t, R3o) and version: message and character counts, plus the residual counts."""
    import json

    import pandas as pd

    from src.replay.variants import build as build_variant, load_item
    rows = []
    for o in items:
        ctx = load_item(o["trace"], int(o["ep_index"]))
        res = residual(ctx)
        for version in ("omission", "correct"):
            content = o["bob_r1_content"] if version == "omission" else None
            for v in ("R1", "R2", "R3", "R3t", "R3o"):
                msgs = build(ctx, v, content) if v in VARIANTS else build_variant(ctx, "CUT" if v == "R1" else v, content)
                rows.append(dict(item_id=o["item_id"], variant=v, version=version, n_messages=len(msgs),
                                 n_chars=len(json.dumps(msgs, ensure_ascii=False)), **res))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    from pathlib import Path

    from src.replay.r5_a13 import omission_items
    out = Path(__file__).resolve().parents[2] / "data" / "derived" / "a15_contexts.csv"
    d = context_table(omission_items())
    d.to_csv(out, index=False)
    print("wrote", out, len(d), "rows")
