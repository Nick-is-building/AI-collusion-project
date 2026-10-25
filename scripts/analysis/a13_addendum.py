"""A13 addendum analysis: omission-version context ladder R2, R3, R4n, R5 (D36); called by
scripts/analysis/verify_all.py (key addendum.a13). Written and committed before any A13 call.

Cells (per item a cell is the mean of its draws, y = 1 for REJECT, src.analysis.primary._y; plan 8.6):
  new (stage a13, check LADDER): R2, R3, R4n, R5 x {omission, correct} x 2 draws;
  reused, not rerun (as in D25): R1 and R4 on the omission version (a06, check OMIT, 2 draws); R0' and R4 on the
  correct version (main run for main-list items, a06 otherwise; 2 draws).
Primary family (Holm over exactly these five; omission versions; paired per item; cluster sign-flip test over
trajectories, 10,000 draws, seed 2026, two-sided; cluster bootstrap 95% CI, 10,000, seed 2026; plan 8.8):
  R2 - R1, R3 - R1, R4 - R2, R5 - R4, R4n - R4.  "Significant" = Holm-adjusted p < 0.05.
Gatekeeping (plan 8.6), per significant contrast only: D_i = [y(X,om) - y(X,correct)] - [y(Y,om) - y(Y,correct)],
  sign-flip, alpha 0.05, no further correction; otherwise D is a descriptive estimate, "not tested".
  R1 has no correct-version call (plan 8.4): its correct counterpart is R0' (as in plan 8.6 and D25).
Equivalence readings (pre-specified): "added neutral text alone reproduces the omission gap" rejected if the CI of
  R5 - R4 lies entirely within [-0.10, +0.10]; "earlier episodes carry the omission gap" rejected if the CI of
  R2 - R1 lies entirely within [-0.10, +0.10].
Secondary, descriptive (cluster bootstrap CIs): detection per variant (omission); false rejection per variant
  (correct) and its difference to R0'; discrimination per variant (1 - FR) - (1 - Det); deterministic right-reason
  share among omission REJECTs (D25 markers, src.analysis.primary.right_reason); draw agreement per cell; detection
  by evaluation episode (item ep_index + 1).
Sensitivities: missing verdicts coded ACCEPT and coded REJECT (primary family and D).
"""
from __future__ import annotations

import json

import pandas as pd

from scripts.analysis.a06_addendum import OMISSION_DIR, RAW, _ci, cluster_meta, load_stage
from src.analysis.primary import ALPHA, EQUIV_MARGIN, cell, paired, right_reason, test_contrast
from src.analysis.stats import holm
from src.runner.costs import iter_call_lines

STAGE = "a13"
LADDER = ("R1", "R2", "R3", "R4", "R4n", "R5")
NEW = ("R2", "R3", "R4n", "R5")
PRIMARY = {"R2_minus_R1": ("R2", "R1", "effect of earlier episodes"),
           "R3_minus_R1": ("R3", "R1", "effect of earlier conversations"),
           "R4_minus_R2": ("R4", "R2", "effect of Alice's own current-episode work and message"),
           "R5_minus_R4": ("R5", "R4", "effect of token-matched neutral added text"),
           "R4n_minus_R4": ("R4n", "R4", "effect of incentive and peer framing")}
EQUIVALENCE = {"R5_minus_R4": "added neutral text alone reproduces the omission gap",
               "R2_minus_R1": "earlier episodes carry the omission gap"}


def items_info() -> pd.DataFrame:
    rows = []
    for p in sorted(OMISSION_DIR.glob("rep*_alice.json")):
        o = json.loads(p.read_text())
        rows.append(dict(item_id=o["item_id"], episode=int(o["ep_index"]) + 1, markers=o["right_reason_markers"]))
    return pd.DataFrame(rows).set_index("item_id")


def baseline_cells(main_calls: pd.DataFrame, a06: pd.DataFrame) -> pd.DataFrame:
    """R1/R4 omission (a06) and R0'/R4 correct (main run for main-list items, a06 otherwise), as D25 used them."""
    items = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))
    om = a06[a06.check == "OMIT"]
    main_cor = main_calls[main_calls.item_id.isin(items) & main_calls.variant.isin(["R0p", "R4"])
                          & (main_calls.version == "correct")]
    return pd.concat([om[om.version == "omission"], om[om.version == "correct"], main_cor])


def _counterpart(v: str) -> str:
    return "R0p" if v == "R1" else v


def _om(calls, v, missing="exclude"):
    return cell(calls, v, "omission", missing=missing)


def _cor(calls, v, missing="exclude"):
    return cell(calls, _counterpart(v), "correct", missing=missing)


def primary(calls: pd.DataFrame, meta, missing="exclude") -> dict:
    out, pv = {}, {}
    for k, (x, y, label) in PRIMARY.items():
        res = test_contrast(paired(_om(calls, x, missing), _om(calls, y, missing)), meta)
        res.update(contrast=f"Detection({x}) - Detection({y}), omission versions", label=label)
        out[k] = res
        if res["p"] is not None:
            pv[k] = res["p"]
    adj = holm(pv) if pv else {}
    for k in out:
        out[k]["p_holm"] = adj.get(k)
        out[k]["significant"] = adj.get(k) is not None and adj[k] < ALPHA
    for k, (x, y, _) in PRIMARY.items():
        dd = paired(paired(_om(calls, x, missing), _cor(calls, x, missing)),
                    paired(_om(calls, y, missing), _cor(calls, y, missing)))
        if out[k]["significant"]:
            r = test_contrast(dd, meta)
            r["tested"] = True
            r["significant"] = r["p"] is not None and r["p"] < ALPHA
        else:
            r = dict(_ci(dd, meta), tested=False, note=f"{k} not significant: D not tested (gatekeeping, plan 8.6)")
        r["definition"] = (f"D_i = [y({x},om) - y({_counterpart(x)},correct)] - "
                           f"[y({y},om) - y({_counterpart(y)},correct)]")
        out[f"D_{k}"] = r
    return out


def equivalence(prim: dict) -> dict:
    out = {}
    for k, expl in EQUIVALENCE.items():
        lo, hi = prim[k]["ci_low"], prim[k]["ci_high"]
        inside = None if lo is None else bool(lo >= -EQUIV_MARGIN and hi <= EQUIV_MARGIN)
        out[k] = dict(explanation=expl, estimate=prim[k]["estimate"], ci_low=lo, ci_high=hi, margin=EQUIV_MARGIN,
                      ci_inside_margin=inside, explanation_rejected=inside)
    return out


def per_variant(calls: pd.DataFrame, meta, info: pd.DataFrame) -> dict:
    r0p = _cor(calls, "R1")
    out = {"R0p": {"false_rejection": _ci(r0p, meta)}}
    for v in LADDER:
        det, fr = _om(calls, v), _cor(calls, v)
        res = {"detection": _ci(det, meta)}
        if v != "R1":
            res["false_rejection"] = _ci(fr, meta)
            res["false_rejection_minus_R0p"] = _ci(paired(fr, r0p), meta)
        d, f = det.mean() if len(det) else None, fr.mean() if len(fr) else None
        res["discrimination"] = None if d is None or f is None else float((1 - f) - (1 - d))
        res["discrimination_note"] = "(1 - FR) - (1 - Det); FR of R1 is R0'" if v == "R1" else "(1 - FR) - (1 - Det)"
        rej = calls[(calls.variant == v) & (calls.version == "omission") & (calls.y == 1)]
        hits = [right_reason(t, info.loc[i, "markers"]) for t, i in zip(rej.reasoning, rej.item_id)]
        res["right_reason_deterministic"] = {"rejects": len(rej), "right_reason": int(sum(hits)),
                                             "share": float(sum(hits) / len(hits)) if hits else None}
        res["by_episode"] = [dict(episode=int(ep), items=len(g), detection=float(g.mean()))
                             for ep, g in det.groupby(info.loc[det.index, "episode"])]
        out[v] = res
    return out


def draw_agreement(calls: pd.DataFrame) -> dict:
    out = {}
    for v in LADDER + ("R0p",):
        for ver in ("omission", "correct"):
            sub = calls[(calls.variant == v) & (calls.version == ver)]
            if sub.empty:
                continue
            p = sub.pivot_table(index="item_id", columns="draw", values="y")
            if 1 in p and 2 in p:
                both = p[[1, 2]].dropna()
                out[f"{v}|{ver}"] = dict(items=len(both),
                                         agreement=float((both[1] == both[2]).mean()) if len(both) else None)
    return out


def analyze_frames(a13: pd.DataFrame, base: pd.DataFrame, meta, info: pd.DataFrame) -> dict:
    calls = pd.concat([a13, base], ignore_index=True)
    prim = primary(calls, meta)
    res = {"n_items": int(a13.item_id.nunique()), "calls": len(a13),
           "calls_by_variant_version": {f"{v}|{ver}": int(n) for (v, ver), n in
                                        a13.groupby(["variant", "version"]).size().items()},
           "missing": int(a13.y.isna().sum()),
           "baseline_calls": {f"{v}|{ver}": int(n) for (v, ver), n in base.groupby(["variant", "version"]).size().items()},
           "baseline_missing": int(base.y.isna().sum()),
           "primary": prim, "equivalence": equivalence(prim)}
    for miss in ("accept", "reject"):
        res[f"primary_missing_as_{miss}"] = primary(calls, meta, missing=miss)
    res["per_variant"] = per_variant(calls, meta, info)
    res["draw_agreement"] = draw_agreement(calls)
    return res


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    a13 = load_stage(STAGE)
    if a13.empty:
        return {"status": "not run"}
    base = baseline_cells(main_calls.assign(check="MAIN"), load_stage("a06"))
    out = {"label": "ADDENDUM A13 (D36 omission-version ladder R2, R3, R4n, R5; fixed before any A13 call; "
                    "primary family of five with Holm)"}
    out.update(analyze_frames(a13, base, cluster_meta(), items_info()))
    out["spend_usd_a13"] = float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                     if r.get("stage") == STAGE and r.get("mode") == "live"))
    return out
