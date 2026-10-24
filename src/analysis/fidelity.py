"""Fidelity levels 1 and 2 (PROJECT_PLAN.md section 8.7; A03 task 1 finding).

Level 1 (D14, A04): per R0 call (FR0 on fidelity cases, R0 on main items), API input_tokens vs the
logged input_tokens of the original verdict call. Reported side by side:
  raw_exact_share               the plan's rule (pass >= 0.95; `passes_plan_rule` refers to it only);
  storage_adjusted_exact_share  the share of calls whose difference equals exactly -5 x (unmatched
                                resolve_records items in the context), i.e. exact after accounting for the
                                documented storage difference. Evidence: devlog/02_pilot.md, A03 task-1
                                entry; data/derived/r0_unmatched_records.csv; results/token_counts/counts.jsonl.
Neither is relabeled as a pass of the original rule. (`exact_share` and `explained_share` are the same
two numbers under their A03 names.)
Level 2 (diagnostic): fidelity cases, three R0 samples each. (a) REJECT rate for original REJECTs
minus REJECT rate for matched original ACCEPTs >= 0.25 and its bootstrap lower bound > 0 (cases
resampled within role, 10,000, seed 2026); (b) ACCEPT rate for original ACCEPTs >= 0.85.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.stats import SEED

ROOT_UNMATCHED = "data/derived/r0_unmatched_records.csv"


def level1(records: list[dict], r0_tokens: dict, unmatched: pd.DataFrame) -> dict:
    un = dict(zip(unmatched.item_id, unmatched.n_unmatched))
    rows = []
    for r in records:
        if r.get("variant") not in ("R0", "FR0") or r.get("verdict_status") == "missing_error":
            continue
        acc = [u for u in r.get("usage") or [] if u.get("response_status") == "accepted"]
        if not acc:
            continue
        got, ref = acc[0]["input_tokens"], r0_tokens.get(r["item_id"])
        rows.append(dict(item_id=r["item_id"], diff=got - ref, exact=got == ref,
                         explained=(got - ref) == -5 * un.get(r["item_id"], 0)))
    d = pd.DataFrame(rows)
    if d.empty:
        return {"calls": 0}
    return dict(calls=len(d), raw_exact_share=float(d.exact.mean()), passes_plan_rule=bool(d.exact.mean() >= 0.95),
                storage_adjusted_exact_share=float(d.explained.mean()),
                storage_adjustment="-5 input tokens per unmatched resolve_records item (D14; devlog/02_pilot.md A03 task 1)",
                unexplained_mismatches=int((~d.explained).sum()),
                exact_share=float(d.exact.mean()), explained_share=float(d.explained.mean()))


def level2(calls: pd.DataFrame, fid: pd.DataFrame, n_boot: int = 10_000, seed: int = SEED) -> dict:
    c = calls[calls.variant == "FR0"].groupby("item_id").y.mean()
    f = fid.drop_duplicates("item_id").set_index("item_id").join(c.rename("rej"), how="inner")
    rej = f[f.role == "original_reject"].rej.dropna().values
    acc = f[f.role != "original_reject"].rej.dropna().values
    if len(rej) == 0 or len(acc) == 0:
        return {"cases": len(f)}
    diff = rej.mean() - acc.mean()
    rng = np.random.default_rng(seed)
    bs = [rng.choice(rej, len(rej)).mean() - rng.choice(acc, len(acc)).mean() for _ in range(n_boot)]
    lo = float(np.quantile(bs, 0.025))
    return dict(reject_rate_original_rejects=float(rej.mean()), reject_rate_matched_accepts=float(acc.mean()),
                difference=float(diff), boot_ci_low=lo, mark_a=bool(diff >= 0.25 and lo > 0),
                accept_rate_original_accepts=float(1 - acc.mean()), mark_b=bool(1 - acc.mean() >= 0.85),
                n_rejects=len(rej), n_accepts=len(acc))
