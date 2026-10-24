"""Item tables for Study 1 (PROJECT_PLAN.md sections 8.1, 8.4, 8.7; assignment A01 task 3).

Built from the raw traces only, before any bait or replay output exists. All randomness uses
numpy.random.default_rng(SEED) with SEED = 2026, consumed in the fixed order documented below.

Procedure (documented in devlog/03_core_experiment.md):
1. Candidates (plan 8.1) from src.reanalysis.candidate_audit, sorted by (trace, ep_index).
   item_id = "<repNNN>_e<evaluation_episode:02d>_alice".
2. Pilot hold-out: rng.choice over extraction candidates (8, without replacement), then over
   data-search candidates (12). Excluded from every confirmatory analysis.
3. Main list: all remaining candidates (61 + 87 = 148 = the plan's cap, so no random drop now;
   a drop is only needed if more than 148 survive bait validation, which cannot happen).
4. Natural-error set: all frame rows with Bob's task incorrect (any task type).
5. Fidelity set: all original REJECT verdicts in the condition (all judges, all episodes) and two
   matched ACCEPTs each, drawn in REJECT order (sorted by trace, ep_index, judge):
   pool = ACCEPT verdicts with the same task type and evaluation episode, not used before;
   first the same trajectory (the other judge in that episode), then rng.choice from other
   trajectories. If the pool is exhausted, the nearest episode (smallest |difference|, then earlier)
   with the same task type is used, and the row is flagged `match_fallback`.

correct_counterpart (plan 8.4): R1 -> R0', R2..R6 and R4n -> same variant on the correct version.

Usage: .venv/bin/python -m src.replay.item_tables
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.reanalysis.candidate_audit import FAMILIES, frame_rows
from src.replay.traces import trace_files, verdict_contexts

SEED = 2026
OUT = Path(__file__).resolve().parents[2] / "data" / "derived" / "items"
CORRECT_COUNTERPART = {"R1": "R0p", "R2": "R2", "R3": "R3", "R4": "R4", "R4n": "R4n", "R5": "R5", "R6": "R6"}
HOLDOUT_N = {"record_extraction": 8, "data_search": 12}


def item_id(trace: str, ep_index: int, judge: str) -> str:
    return f"{trace.split('.')[0]}_e{ep_index + 1:02d}_{judge}"


def all_verdicts() -> pd.DataFrame:
    rows = []
    for f in trace_files():
        for v in verdict_contexts(f.name):
            rows.append(dict(trace=v.trace, run_id=v.run_id, ep_index=v.ep_index,
                             evaluation_episode=v.evaluation_episode, judge=v.judge, task_type=v.task_type,
                             peer_correct=v.peer_correct, verdict=v.verdict,
                             verdict_prompt_idx=v.verdict_prompt_idx))
    return pd.DataFrame(rows).sort_values(["trace", "ep_index", "judge"]).reset_index(drop=True)


def build(rng=None):
    rng = rng or np.random.default_rng(SEED)
    frame = frame_rows().sort_values(["trace", "ep_index"]).reset_index(drop=True)
    frame["item_id"] = [item_id(t, e, "alice") for t, e in zip(frame.trace, frame.ep_index)]
    cand = frame[frame.peer_correct & frame.task_type.isin(FAMILIES)].copy()
    hold = []
    for fam in ("record_extraction", "data_search"):
        ids = cand.loc[cand.task_type == fam, "item_id"].tolist()
        hold += list(rng.choice(ids, size=HOLDOUT_N[fam], replace=False))
    cand["set"] = np.where(cand.item_id.isin(hold), "pilot_holdout", "main")
    cand["correct_counterpart"] = json.dumps(CORRECT_COUNTERPART)
    natural = frame[~frame.peer_correct].copy()
    natural["set"] = "natural_error"
    natural["error_type"] = [
        ("omission" if m and not x else "commission" if x and not m else "both" if m and x else "none")
        if t == "record_extraction" else t
        for t, m, x in zip(natural.task_type, natural.ext_missing, natural.ext_extra)]

    v = all_verdicts()
    v["item_id"] = [item_id(t, e, j) for t, e, j in zip(v.trace, v.ep_index, v.judge)]
    rej = v[v.verdict == "reject"]
    acc = v[v.verdict == "accept"]
    used = set()
    fid = []
    for r in rej.itertuples():
        fid.append(dict(item_id=r.item_id, role="original_reject", matched_to=None, match_level="self"))
        for _ in range(2):
            pool = acc[(acc.task_type == r.task_type) & ~acc.item_id.isin(used)]
            same_ep = pool[pool.evaluation_episode == r.evaluation_episode]
            same_tr = same_ep[same_ep.trace == r.trace]
            if len(same_tr):
                pick, level = same_tr.item_id.iloc[0], "same_trajectory_same_episode"
            elif len(same_ep):
                pick, level = rng.choice(same_ep.item_id.tolist()), "same_episode"
            else:
                d = (pool.evaluation_episode - r.evaluation_episode)
                best = pool.assign(dist=d.abs(), later=(d > 0)).sort_values(["dist", "later", "item_id"])
                pick, level = best.item_id.iloc[0], "match_fallback_nearest_episode"
            used.add(pick)
            fid.append(dict(item_id=pick, role="matched_accept", matched_to=r.item_id, match_level=level))
    fid = pd.DataFrame(fid).merge(v, on="item_id", how="left")
    return cand, natural, fid


def main():
    cand, natural, fid = build()
    OUT.mkdir(parents=True, exist_ok=True)
    keep = ["item_id", "set", "trace", "run_id", "ep_index", "evaluation_episode", "task_type", "peer_task_id",
            "peer_correct", "verdict", "cut_idx", "verdict_prompt_idx", "verdict_input_tokens", "response_model",
            "correct_counterpart"]
    cand[keep].to_csv(OUT / "candidates.csv", index=False)
    natural[[k for k in keep if k != "correct_counterpart"] + ["error_type", "ext_missing", "ext_extra",
                                                                "ds_missing", "ds_extra"]].to_csv(
        OUT / "natural_error_set.csv", index=False)
    fid.to_csv(OUT / "fidelity_set.csv", index=False)
    print("candidates:", cand.groupby(["set", "task_type"]).size().to_dict())
    print("holdout trajectories:", cand[cand.set == "pilot_holdout"].trace.nunique())
    print("natural-error set:", len(natural), natural.error_type.value_counts().to_dict())
    print("fidelity set:", fid.role.value_counts().to_dict(), fid.match_level.value_counts().to_dict())
    print("fidelity matched accepts unique:", fid[fid.role == "matched_accept"].item_id.nunique())


if __name__ == "__main__":
    main()
