"""A15 addendum analysis: history decomposition R3t ("earlier work only") and R3o ("earlier outcomes only") (D38;
exploratory follow-up of A13); called by scripts/analysis/verify_all.py (key addendum.a15). Written and committed
before any A15 call.

Cells (per item a cell is the mean of its draws, y = 1 for REJECT; plan 8.6):
  new (stage a15, check HIST): R3t, R3o x {omission, correct} x 2 draws;
  reused, never rerun: R1 (omission) and R0' (correct) as in D25 (a06; main run for main-list items), R2 and R3
  (omission and correct; A13, check LADDER).
Primary family (Holm over exactly two; omission versions; paired per item; cluster sign-flip over trajectories,
10,000, seed 2026, two-sided; cluster bootstrap 95%, 10,000, seed 2026):
  H_out  = Detection(R3t) - Detection(R3)   (effect of removing the outcome history)
  H_work = Detection(R3o) - Detection(R3)   (effect of removing the earlier task work)
  "Significant" = Holm-adjusted p < 0.05. Gatekeeping per significant test (plan 8.6):
  D_i = [y(X,om) - y(X,correct)] - [y(R3,om) - y(R3,correct)], sign-flip, alpha 0.05; otherwise D descriptive.
  Equivalence flag: 95% CI inside [-0.10, +0.10].
Secondary, descriptive (cluster bootstrap CIs): R3t and R3o each minus R1 and minus R2 (omission); false rejection per
  variant and minus R0'; tokens: per item and variant the API-reported input_tokens of the first accepted request
  (omission version, mean over draws), removed tokens = tokens(R1) - tokens(variant), for R1, R3, R3t, R3o, R2, with
  detection per variant (scatter data; no model is fitted); named_accept (ACCEPT whose reasoning contains the removed
  ID or sentence, D25 markers) and deterministic right-reason share among omission REJECTs per variant.
Sensitivities: missing verdicts coded ACCEPT and REJECT (primary family and D).
"""
from __future__ import annotations

import json
from statistics import median

import pandas as pd

from scripts.analysis.a06_addendum import RAW, _ci, cluster_meta, load_stage
from scripts.analysis.a13_addendum import baseline_cells, items_info
from src.analysis.primary import ALPHA, EQUIV_MARGIN, cell, paired, right_reason, test_contrast
from src.analysis.stats import holm
from src.runner.costs import iter_call_lines

STAGE = "a15"
LADDER = ("R1", "R3", "R3t", "R3o", "R2")
PRIMARY = {"H_out": ("R3t", "effect of removing the outcome history (earlier verdicts, feedback, reflections)"),
           "H_work": ("R3o", "effect of removing the earlier task work")}


def _counterpart(v: str) -> str:
    return "R0p" if v == "R1" else v


def _om(calls, v, missing="exclude"):
    return cell(calls, v, "omission", missing=missing)


def _cor(calls, v, missing="exclude"):
    return cell(calls, _counterpart(v), "correct", missing=missing)


def primary(calls: pd.DataFrame, meta, missing="exclude") -> dict:
    out, pv = {}, {}
    for k, (x, label) in PRIMARY.items():
        res = test_contrast(paired(_om(calls, x, missing), _om(calls, "R3", missing)), meta)
        res.update(contrast=f"Detection({x}) - Detection(R3), omission versions", label=label)
        lo, hi = res["ci_low"], res["ci_high"]
        res["ci_inside_equivalence_margin"] = None if lo is None else bool(lo >= -EQUIV_MARGIN and hi <= EQUIV_MARGIN)
        out[k] = res
        if res["p"] is not None:
            pv[k] = res["p"]
    adj = holm(pv) if pv else {}
    for k in PRIMARY:
        out[k]["p_holm"] = adj.get(k)
        out[k]["significant"] = adj.get(k) is not None and adj[k] < ALPHA
        x = PRIMARY[k][0]
        dd = paired(paired(_om(calls, x, missing), _cor(calls, x, missing)),
                    paired(_om(calls, "R3", missing), _cor(calls, "R3", missing)))
        if out[k]["significant"]:
            r = test_contrast(dd, meta)
            r["tested"] = True
            r["significant"] = r["p"] is not None and r["p"] < ALPHA
        else:
            r = dict(_ci(dd, meta), tested=False, note=f"{k} not significant: D not tested (gatekeeping, plan 8.6)")
        r["definition"] = f"D_i = [y({x},om) - y({x},correct)] - [y(R3,om) - y(R3,correct)]"
        out[f"D_{k}"] = r
    out["equivalence_margin"] = EQUIV_MARGIN
    return out


def input_tokens_by_call(stages=("a06", "a13", STAGE)) -> dict:
    """call_id -> input_tokens of the first accepted request (usage record without error), live lines only."""
    out = {}
    for r in iter_call_lines(RAW):
        if r.get("mode") != "live" or r.get("stage") not in stages:
            continue
        acc = [u for u in (r.get("usage") or []) if not u.get("error_category") and u.get("input_tokens") is not None]
        if acc:
            out[r["call_id"]] = int(acc[0]["input_tokens"])
    return out


def token_table(calls: pd.DataFrame, tokens: dict) -> pd.DataFrame:
    """Per item and variant (omission versions): mean input tokens over draws, removed tokens vs R1."""
    sub = calls[(calls.version == "omission") & calls.variant.isin(LADDER)].copy()
    sub["tokens"] = sub.call_id.map(tokens)
    t = sub.dropna(subset=["tokens"]).groupby(["item_id", "variant"]).tokens.mean().unstack()
    rem = t.rsub(t["R1"], axis=0) if "R1" in t else t * float("nan")
    return t.join(rem.add_prefix("removed_"))


def secondary(calls: pd.DataFrame, meta, info: pd.DataFrame, tokens: dict) -> dict:
    r0p = _cor(calls, "R1")
    out = {"contrasts": {}, "per_variant": {"R0p": {"false_rejection": _ci(r0p, meta)}}}
    for x in ("R3t", "R3o"):
        for y in ("R1", "R2"):
            out["contrasts"][f"{x}_minus_{y}"] = _ci(paired(_om(calls, x), _om(calls, y)), meta)
    tt = token_table(calls, tokens)
    for v in LADDER:
        det, fr = _om(calls, v), _cor(calls, v)
        res = {"detection": _ci(det, meta)}
        if v != "R1":
            res["false_rejection"] = _ci(fr, meta)
            res["false_rejection_minus_R0p"] = _ci(paired(fr, r0p), meta)
        om = calls[(calls.variant == v) & (calls.version == "omission")]
        rej, acc = om[om.y == 1], om[om.y == 0]
        hit = [right_reason(t, info.loc[i, "markers"]) for t, i in zip(rej.reasoning, rej.item_id)]
        named = [right_reason(t, info.loc[i, "markers"]) for t, i in zip(acc.reasoning, acc.item_id)]
        res["right_reason_deterministic"] = {"rejects": len(rej), "right_reason": int(sum(hit))}
        res["named_accept"] = {"accepts": len(acc), "named_accept": int(sum(named)),
                               "calls_omission": len(om) - int(om.y.isna().sum())}
        if v in tt:
            col = tt[v].dropna()
            res["tokens"] = {"items": len(col), "median": float(median(col)), "min": float(col.min()),
                             "max": float(col.max())}
            rcol = tt[f"removed_{v}"].dropna()
            res["removed_tokens_vs_R1"] = {"items": len(rcol), "median": float(median(rcol)),
                                           "min": float(rcol.min()), "max": float(rcol.max())}
        out["per_variant"][v] = res
    out["scatter_detection_vs_removed_tokens"] = {
        "note": "per variant: median removed tokens (vs R1, omission version) and detection; no model is fitted",
        "points": [dict(variant=v, median_removed_tokens=out["per_variant"][v].get("removed_tokens_vs_R1", {}).get("median"),
                        detection=out["per_variant"][v]["detection"]["estimate"]) for v in LADDER]}
    out["token_table_per_item"] = [dict(item_id=i, **{k: (None if pd.isna(x) else float(x)) for k, x in r.items()})
                                   for i, r in tt.iterrows()]
    return out


def analyze_frames(a15: pd.DataFrame, base: pd.DataFrame, meta, info: pd.DataFrame, tokens: dict) -> dict:
    calls = pd.concat([a15, base], ignore_index=True)
    res = {"n_items": int(a15.item_id.nunique()), "calls": len(a15),
           "calls_by_variant_version": {f"{v}|{ver}": int(n) for (v, ver), n in
                                        a15.groupby(["variant", "version"]).size().items()},
           "missing": int(a15.y.isna().sum()), "baseline_missing": int(base.y.isna().sum()),
           "primary": primary(calls, meta)}
    for miss in ("accept", "reject"):
        res[f"primary_missing_as_{miss}"] = primary(calls, meta, missing=miss)
    res["secondary"] = secondary(calls, meta, info, tokens)
    return res


def baselines(main_calls: pd.DataFrame) -> pd.DataFrame:
    base = baseline_cells(main_calls.assign(check="MAIN"), load_stage("a06"))
    base = base[base.variant.isin(["R1", "R0p"])]
    a13 = load_stage("a13")
    return pd.concat([base, a13[a13.variant.isin(["R2", "R3"])]], ignore_index=True)


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    a15 = load_stage(STAGE)
    if a15.empty:
        return {"status": "not run"}
    out = {"label": "ADDENDUM A15 (D38 history decomposition R3t, R3o; exploratory follow-up of A13; fixed before any "
                    "A15 call; primary family of two with Holm)"}
    out.update(analyze_frames(a15, baselines(main_calls), cluster_meta(), items_info(), input_tokens_by_call()))
    out["spend_usd_a15"] = float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                     if r.get("stage") == STAGE and r.get("mode") == "live"))
    return out
