"""A17 addendum analysis (D41): Claude Haiku 5.5 judging in Gemini 3.1 Flash-Lite's trajectories (cross-family; Gemini
thought signatures removed), on the identical D25 contexts; exploratory cross-family transfer study, the same design as
D39 (A16). Called by scripts/analysis/verify_all.py (key addendum.a17). Written and committed before any A17 call.

Reuse (identical analysis to D39): the primary family, gatekeeping, interpretation rows and secondaries are A16's own
functions (scripts.analysis.a16_addendum.primary / interpretation / secondary), applied to the A17 calls frame (stage
a17, check HAIKU; the P6 check is not analysed here). Same cells (no commission cell in A17; A16's R1-com entry is
therefore empty in `secondary`).
  G = Detection(R4) - Detection(R1);  H = Detection(R2) - Detection(R1);  C = Detection(R1+CHK) - Detection(R1);
  Holm over exactly three, "significant" = Holm p < 0.05; gatekeeping D per significant contrast; rows 1-6 of D39.
Item sets: primary = the 50 D25 items minus rep041_e06 and rep044_e03 (the 2 genuine residues, D40; the same set as
A16's primary set, read from A16's frozen data/derived/a16/primary_exclusions.json and asserted equal); sensitivities:
all 50 items, and without all 4 D40-flagged items.
Verifier comparisons (descriptive, paired by item, cluster bootstrap CI, no test): every cell and G, H, C,
  Haiku minus Flash-Lite (the existing Flash-Lite cells, a16_addendum.flash_lite_frame), and Haiku minus 3.8 Flash
  (stage a16 lines) if A16 has finished (all its XVER call IDs logged); otherwise "A16 not finished".
Also: served-model evidence (response models of all usage records), thinking evidence and usage per call (output and
reasoning tokens as logged), the P6 result, spend.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.analysis import a16_addendum as A16
from scripts.analysis.a06_addendum import RAW, _ci, cluster_meta, load_stage
from scripts.analysis.a13_addendum import items_info
from src.analysis.primary import cell, paired
from src.replay import a17
from src.runner.costs import iter_call_lines
from src.runner.runner import normalize_model

ROOT = Path(__file__).resolve().parents[2]
STAGE, CHECK = "a17", "HAIKU"
CELLS = A16.OM_CELLS + A16.COR_CELLS
EXPECTED_PRIMARY_EXCLUSIONS = ["rep041_e06_alice", "rep044_e03_alice"]


def comparison(x: pd.DataFrame, other: pd.DataFrame, meta, name: str) -> dict:
    out = {"cells": {}, "contrasts": {}}
    for v, ver in CELLS:
        a, b = cell(x, v, ver), cell(other, v, ver)
        out["cells"][f"{v}|{ver}"] = {"haiku": _ci(a, meta), name: _ci(b, meta), "difference": _ci(paired(a, b), meta)}
    for k, (xv, _) in A16.PRIMARY.items():
        a, b = A16.contrast_series(x, xv), A16.contrast_series(other, xv)
        out["contrasts"][k] = {"haiku": _ci(a, meta), name: _ci(b, meta), "difference": _ci(paired(a, b), meta)}
    return out


def block(x: pd.DataFrame, fl: pd.DataFrame, f38, meta, info, items: list[str]) -> dict:
    x = x[x.item_id.isin(items)]
    fl = fl[fl.item_id.isin(items)]
    res = {"n_items": int(x.item_id.nunique()),
           "n_clusters": int(meta.loc[sorted(set(x.item_id)), "cluster"].nunique()) if len(x) else 0,
           "primary": A16.primary(x, meta)}
    for miss in ("accept", "reject"):
        res[f"primary_missing_as_{miss}"] = A16.primary(x, meta, missing=miss)
    res["interpretation"] = A16.interpretation(x, meta, res["primary"])
    res["haiku_minus_flash_lite"] = comparison(x, fl, meta, "flash_lite")
    res["haiku_minus_flash_38"] = (comparison(x, f38[f38.item_id.isin(items)], meta, "flash_38")
                                   if f38 is not None else {"status": "A16 not finished"})
    res["secondary"] = A16.secondary(x, meta, info)
    return res


def a16_frame():
    """Stage a16 XVER calls if A16 has finished, else None. Finished = every call ID of its list is logged, for the
    full list or for one of A16's pre-specified drop levels (a; a+b; a+b+c), whichever applies."""
    from scripts.a16.launch_a16 import jobs as a16_jobs
    f = load_stage("a16")
    if f.empty:
        return None
    logged = set(f.call_id)
    for drop in ("", "a", "a b", "a b c"):
        want = {j.call_id("a16") for j in a16_jobs(drop=drop)}
        if want <= logged:
            return f[f.call_id.isin(want)]
    return None


def evidence(raw=RAW) -> dict:
    """Served models, thinking and usage over all live a17 lines (HAIKU and P6)."""
    models, acc, n = Counter(), Counter(), 0
    think_calls, out_tok, reas_tok, n_usage = 0, [], [], 0
    for r in iter_call_lines(raw):
        if r.get("stage") != STAGE or r.get("mode") != "live":
            continue
        n += 1
        for m in r.get("response_models") or []:
            models[m] += 1
        for u in r.get("usage") or []:
            if u.get("response_model") and not u.get("error_category"):
                acc[normalize_model(u["response_model"])] += 1
                n_usage += 1
                if u.get("billable_output_tokens") is not None:
                    out_tok.append(u["billable_output_tokens"])
                if u.get("reasoning_tokens") is not None:
                    reas_tok.append(u["reasoning_tokens"])
        msgs = r.get("response_messages") or []
        think_calls += any(m.get("thinking_blocks") or m.get("reasoning_content")
                           for m in msgs if m.get("role") == "assistant")
    med = lambda v: float(pd.Series(v).median()) if v else None
    return {"call_lines": n, "response_models_entries": dict(models), "accepted_responses_by_model": dict(acc),
            "only_expected_model": set(acc) <= {a17.SERVED_MODEL} and set(map(normalize_model, models)) <= {a17.SERVED_MODEL},
            "calls_with_thinking_in_response": think_calls, "accepted_responses": n_usage,
            "median_billable_output_tokens": med(out_tok), "median_reasoning_tokens_logged": med(reas_tok)}


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    exc = A16.load_exclusions()
    if exc is None or sorted(exc["excluded"]) != EXPECTED_PRIMARY_EXCLUSIONS:
        raise RuntimeError(f"A16 exclusion file missing or not the A17 primary set: {exc and exc.get('excluded')}")
    st = load_stage(STAGE)
    if st.empty:
        return {"status": "not run", "label": a17.LABEL}
    from scripts.a17.launch_a17 import p6_check
    x = st[st.check == CHECK]
    out = {"label": "ADDENDUM A17 (D41; exploratory cross-family transfer, same design as D39): " + a17.LABEL,
           "exclusions": {"primary_excluded": exc["excluded"], "d40_flagged": exc["d40"]["flagged_items"],
                          "source": "data/derived/a16/primary_exclusions.json (A16's frozen file)"},
           "p6": p6_check(RAW), "evidence": evidence()}
    if x.empty:
        out["status"] = "P6 only"
        return out
    meta, info = cluster_meta(), items_info()
    fl = A16.flash_lite_frame(main_calls)
    f38 = a16_frame()
    all_items = sorted(o["item_id"] for o in a17_items())
    prim = [i for i in all_items if i not in set(exc["excluded"])]
    out.update(calls=len(x), missing=int(x.y.isna().sum()),
               calls_by_cell={f"{v}|{ver}": int(n) for (v, ver), n in x.groupby(["variant", "version"]).size().items()},
               a16_finished=f38 is not None,
               primary_item_set=block(x, fl, f38, meta, info, prim),
               all_50_sensitivity=block(x, fl, f38, meta, info, all_items),
               without_all_d40_flagged_sensitivity=block(
                   x, fl, f38, meta, info, [i for i in all_items if i not in set(exc["d40"]["flagged_items"])]))
    out["spend_usd_a17"] = float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                     if r.get("stage") == STAGE and r.get("mode") == "live"))
    return out


def a17_items():
    from scripts.a06.launch_addendum import omission_items
    return omission_items()


if __name__ == "__main__":
    print(json.dumps(analyze(pd.DataFrame(), pd.DataFrame()), indent=1, default=str)[:2000])
