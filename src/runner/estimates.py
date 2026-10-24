"""Token estimates for cost projection and fail-closed pre-checks (no token-counting calls).

Input tokens:
- R0: the logged `input_tokens` of the original verdict call (candidates: column
  verdict_input_tokens of data/derived/verdict_frame_flash_lite_unconstrained_exact_rule.csv;
  fidelity items: the accepted verdict usage record of that judge in the trace).
- Other variants: R0 tokens x chars(variant) / chars(R0) for the same item, where chars = canonical
  JSON of the built message list with thought signatures stripped (cached in scratch/). Rough
  proportional estimate: JSON overhead differs by message type, tool schemas are not in chars.
  Bait versions use the correct-version value.
Output tokens: verdict calls of all 50 original traces (1,000 calls, provider_output_tokens incl.
thinking): p50 120, p95 1,146, max 3,623 (measured 2026-10-24). Projections use p95 per call;
the fail-closed pre-check uses OUTPUT_TOKENS_PRECHECK = 4,000 per attempt, all 3 verdict attempts,
and INPUT_MARGIN = 1.10 on input.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "data" / "derived" / "verdict_frame_flash_lite_unconstrained_exact_rule.csv"
FIDELITY = ROOT / "data" / "derived" / "items" / "fidelity_set.csv"

OUTPUT_TOKENS_P95 = 1146
OUTPUT_TOKENS_PRECHECK = 4000
INPUT_MARGIN = 1.10
VERDICT_ATTEMPTS = 3
# variant name used for the chars ratio
CHARS_VARIANT = {"R0": "R0", "R0p": "CUT", "CUT": "CUT", "R1": "CUT", "R2": "R2", "R3": "R3", "R4": "R4",
                 "R4n": "R4n", "R5": "CUT", "R6": "CUT"}  # R5 is matched to R1's length; R6 ~ R1


@lru_cache(maxsize=1)
def r0_tokens() -> dict:
    out = {}
    f = pd.read_csv(FRAME)
    for r in f.itertuples():
        out[f"{r.trace.split('.')[0]}_e{r.ep_index + 1:02d}_alice"] = int(r.verdict_input_tokens)
    from src.replay.traces import load_trace, verdict_usage
    for r in pd.read_csv(FIDELITY).itertuples():
        if r.item_id in out:
            continue
        use = verdict_usage(load_trace(r.trace), r.ep_index, r.judge)
        acc = [u for u in use if u.get("response_status") == "accepted"] or use
        out[r.item_id] = int(acc[0]["input_tokens"])
    return out


CACHE = ROOT / "scratch" / "estimates_nosig_chars.json"
_nosig: dict | None = None


def _strip_signatures(messages: list) -> list:
    out = json.loads(json.dumps(messages))
    for m in out:
        m.pop("provider_specific_fields", None)
        for tc in m.get("tool_calls") or []:
            tc["id"] = tc["id"].split("__thought__")[0]
            tc.pop("provider_specific_fields", None)
    return out


def nosig_chars(item_id: str, variant: str) -> int:
    """Characters of the canonical JSON of the variant's messages without thought signatures
    (signatures are opaque and make up about a third of long contexts' characters)."""
    global _nosig
    if _nosig is None:
        _nosig = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    key = f"{item_id}|{variant}"
    if key not in _nosig:
        from src.replay.request import canonical_json
        from src.replay.variants import build, load_item
        rep, ep, judge = item_id.split("_")
        ctx = load_item(f"{rep}.json.gz", int(ep[1:]) - 1, judge)
        _nosig[key] = len(canonical_json(_strip_signatures(build(ctx, variant))))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(_nosig))
    return _nosig[key]


def input_tokens(item_id: str, variant: str) -> int:
    base = r0_tokens()[item_id]
    if variant == "R0":
        return base
    v = CHARS_VARIANT[variant]
    return int(round(base * nosig_chars(item_id, v) / nosig_chars(item_id, "R0")))


def projected_call_cost(prices, model: str, in_tokens: int) -> float:
    """Expected cost of one verdict call (one attempt, p95 output) for projections."""
    return prices.cost(model, in_tokens, 0, OUTPUT_TOKENS_P95)


def precheck_cost(prices, model: str, in_tokens: int) -> float:
    """Conservative worst case for one verdict job: all attempts, generous output, no cache."""
    per = prices.cost(model, int(in_tokens * INPUT_MARGIN) + VERDICT_ATTEMPTS * 500, 0, OUTPUT_TOKENS_PRECHECK)
    return VERDICT_ATTEMPTS * per
