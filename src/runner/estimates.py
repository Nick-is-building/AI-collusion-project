"""Token estimates for cost projection and fail-closed pre-checks (no token-counting calls).

Input tokens:
- R0: the logged `input_tokens` of the original verdict call (candidates: column
  verdict_input_tokens of data/derived/verdict_frame_flash_lite_unconstrained_exact_rule.csv;
  fidelity items: the accepted verdict usage record of that judge in the trace).
- Other variants: R0 tokens x chars(variant) / chars(R0) for the same item, chars from
  data/derived/dryrun_request_hashes.csv (canonical JSON of the message list). This is a rough
  proportional estimate: base64 thought signatures and JSON overhead inflate chars, tool schemas
  are not in chars, and R4n's system prompt differs. Bait versions use the correct-version value.
Output tokens: verdict calls of all 50 original traces (1,000 calls, provider_output_tokens incl.
thinking): p50 120, p95 1,146, max 3,623 (measured 2026-10-24). Projections use p95 per call;
the fail-closed pre-check uses OUTPUT_TOKENS_PRECHECK = 4,000 per attempt, all 3 verdict attempts,
and INPUT_MARGIN = 1.10 on input.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / "data" / "derived" / "verdict_frame_flash_lite_unconstrained_exact_rule.csv"
DRYRUN = ROOT / "data" / "derived" / "dryrun_request_hashes.csv"
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


@lru_cache(maxsize=1)
def chars_table() -> dict:
    d = pd.read_csv(DRYRUN)
    return {(r.item_id, r.variant): int(r.chars) for r in d.itertuples()}


@lru_cache(maxsize=None)
def median_ratio(variant: str) -> float:
    """Median chars(variant)/chars(R0) over items with both in the dry run (fallback)."""
    ch = chars_table()
    ratios = sorted(ch[(i, variant)] / ch[(i, "R0")] for (i, v) in ch if v == variant and (i, "R0") in ch)
    return ratios[len(ratios) // 2]


def input_tokens(item_id: str, variant: str) -> int:
    base = r0_tokens()[item_id]
    if variant == "R0":
        return base
    ch = chars_table()
    v = CHARS_VARIANT[variant]
    if (item_id, v) in ch and (item_id, "R0") in ch:
        return int(round(base * ch[(item_id, v)] / ch[(item_id, "R0")]))
    return int(round(base * median_ratio(v)))  # e.g. natural-error items (not in the dry run)


def projected_call_cost(prices, model: str, in_tokens: int) -> float:
    """Expected cost of one verdict call (one attempt, p95 output) for projections."""
    return prices.cost(model, in_tokens, 0, OUTPUT_TOKENS_P95)


def precheck_cost(prices, model: str, in_tokens: int) -> float:
    """Conservative worst case for one verdict job: all attempts, generous output, no cache."""
    per = prices.cost(model, int(in_tokens * INPUT_MARGIN) + VERDICT_ATTEMPTS * 500, 0, OUTPUT_TOKENS_PRECHECK)
    return VERDICT_ATTEMPTS * per
