"""Verdict jobs for every replay variant, and the main-run job list (PROJECT_PLAN.md 8.4, 8.6, 8.7, 12).

Variant -> context (src.replay.variants / r5 / r6), version:
  R0   original prefix, correct only            R0p  cut context (= CUT), correct only
  R1   cut context with the bait, bait only     R2, R3, R4, R4n   both versions
  R5   R4 + matched filler (data/derived/r5_fillers.csv), both versions
  R6   cut context (R1 on bait, R0' on correct) + one verdict-prompt sentence (D13) + itemization gate
       (src.replay.r6), both versions
  N1   cut context on a natural-error item       N4   R4 context on a natural-error item (no bait)
  FR0  R0 on a fidelity case (judge alice or bob)

Main-run list (`main_run_jobs`), all Gemini 3.1 Flash-Lite:
  per main item (19 calls): bait R1 x2, R2, R3, R4 x2, R4n, R5, R6; correct R0, R0p x2, R2, R3, R4 x2,
  R4n, R5, R6 (two draws for the four primary cells R1-bait, R0', R4-bait, R4-correct; plan 8.6);
  natural-error set: N1, N4 per item; fidelity set: FR0 x 3 samples per case (plan 8.7).
  Order: items in a seeded random order; within an item all its calls are adjacent, in a seeded random
  order (plan 8.5: calls for all variants of an item run close in time, variant order shuffled).
  Seed: numpy default_rng(2026) consumed as: permutation of main items, then one permutation per item
  in that order, then permutation of natural-error items, then of fidelity cases.
Not in the list: R1-live (no driver yet, build step 6), Haiku (P6 not run), Gemini 3.7 Flash.
"""
from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
import pandas as pd

from src.replay.r5 import build_r5
from src.replay.r6 import run_r6, with_prompt_sentence
from src.replay.traces import episode_bounds, get_log_raw, load_trace
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.item_lists import (ITEMS, SEED, load_bait, main_items, natural_error_items)
from src.runner.runner import Job

ROOT = Path(__file__).resolve().parents[2]
R5_TABLE = ROOT / "data" / "derived" / "r5_fillers.csv"
MODEL = "gemini/gemini-3.1-flash-lite"

BAIT_CELLS = [("R1", 1), ("R1", 2), ("R2", 1), ("R3", 1), ("R4", 1), ("R4", 2), ("R4n", 1), ("R5", 1), ("R6", 1)]
CORRECT_CELLS = [("R0", 1), ("R0p", 1), ("R0p", 2), ("R2", 1), ("R3", 1), ("R4", 1), ("R4", 2), ("R4n", 1),
                 ("R5", 1), ("R6", 1)]
EST_VARIANT = {"R0": "R0", "R0p": "CUT", "R1": "CUT", "R2": "R2", "R3": "R3", "R4": "R4", "R4n": "R4n",
               "R5": "R5", "R6": "R6", "N1": "CUT", "N4": "R4", "FR0": "R0"}


@functools.lru_cache(maxsize=1)
def r5_table() -> dict:
    if not R5_TABLE.exists():
        return {}
    d = pd.read_csv(R5_TABLE)
    return {(r.item_id, r.version): int(r.n_chars) for r in d.itertuples() if bool(r.within_tolerance)}


def original_bob_message(trace: str, ep_index: int) -> tuple[str, str]:
    """(Bob's round-1 message content as Alice saw it, Bob's raw log) on the correct version."""
    ctx = load_item(trace, ep_index)
    t = load_trace(trace)
    raw = get_log_raw(t["results"][ep_index]["agents"]["bob"]["messages"], *episode_bounds(t, ep_index, "bob"))
    return ctx.messages[ctx.cut_idx]["content"], raw


def make_job(check: str, row, variant: str, version: str = "correct", draw: int = 1, judge: str = "alice",
             model: str = MODEL) -> Job:
    trace, ep, item = row.trace, int(row.ep_index), row.item_id
    if version == "bait":
        if variant in ("R0", "R0p", "N1", "N4", "FR0"):
            raise ValueError(f"{variant} runs on correct versions only")
        bait = load_bait(item)
        content, raw = bait["bob_r1_content"], bait["bait_raw_log"]
    else:
        if variant == "R1":
            raise ValueError("R1 has no correct-version call (counterpart R0p)")
        content, raw = None, None
    verdict_fn = None
    if variant == "R5":
        def builder():
            n = r5_table().get((item, version))
            if n is None:   # fail closed at run time: no matched filler, no call
                raise KeyError(f"no matched R5 filler for {item} {version}")
            return build_r5(load_item(trace, ep), n, bob_r1_content=content)
    elif variant in ("R0", "FR0"):
        def builder():
            return build(load_item(trace, ep, judge), "R0")
    else:
        bv = {"R0p": "CUT", "R1": "CUT", "R6": "CUT", "N1": "CUT", "N4": "R4"}.get(variant, variant)

        def builder():
            msgs = build(load_item(trace, ep), bv, bob_r1_content=content)
            return with_prompt_sentence(msgs) if variant == "R6" else msgs   # D13
    if variant == "R6":
        if content is None:
            content, raw = original_bob_message(trace, ep)
        verdict_fn = functools.partial(run_r6, bob_r1_content=content, raw_log=raw)
    est = input_tokens(item, EST_VARIANT[variant])
    if variant == "R6":
        est *= 2   # the fail-closed pre-check covers the gate retry (a second verdict phase)
    return Job(check=check, item_id=item, variant=variant, version=version, draw=draw, judge=judge,
               task_type=row.task_type, build_messages=builder, est_input_tokens=est, model=model,
               verdict_fn=verdict_fn)


def main_run_jobs(check: str = "MAIN") -> list[Job]:
    rng = np.random.default_rng(SEED)
    jobs = []
    main = main_items()
    for i in rng.permutation(len(main)):
        row = main.iloc[i]
        cells = [("bait", v, d) for v, d in BAIT_CELLS] + [("correct", v, d) for v, d in CORRECT_CELLS]
        for k in rng.permutation(len(cells)):
            version, v, d = cells[k]
            jobs.append(make_job(check, row, v, version, d))
    nat = natural_error_items()
    for i in rng.permutation(len(nat)):
        row = nat.iloc[i]
        jobs += [make_job(check, row, "N1"), make_job(check, row, "N4")]
    fid = pd.read_csv(ITEMS / "fidelity_set.csv").drop_duplicates("item_id").reset_index(drop=True)
    for i in rng.permutation(len(fid)):
        row = fid.iloc[i]
        jobs += [make_job(check, row, "FR0", "correct", d, judge=row.judge) for d in (1, 2, 3)]
    return jobs
