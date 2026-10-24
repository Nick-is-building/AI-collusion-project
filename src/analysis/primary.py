"""Study 1 estimands and tests (PROJECT_PLAN.md sections 8.6, 8.8; deviations D2, D6-D12).

Input: one row per verdict call (`calls` DataFrame; `load_calls` reads the runner's JSONL lines) with
item_id, variant, version, draw, verdict_status, verdict, reasoning, extra (R6 outcomes), and item
metadata (`item_meta`: cluster = trajectory, task_type, episode, bob_states_condition, markers).

Outcome y = 1 for REJECT, 0 for ACCEPT, missing (NaN) if verdict_status != "ok" (plan 13: missing_error
and missing_forced are missing). Missing-verdict sensitivity: missing coded as ACCEPT (0) and as
REJECT (1) (plan 8.8).

Cell value per item: mean of y over the draws present (two draws for R1-bait, R0', R4-bait, R4-correct,
plan 8.6; otherwise one). An item whose draws are all missing has no value in that cell.

Contrasts (plan 8.8): d_i = value_i(X) - value_i(Y) over items with both values (pairwise exclusion);
statistic = mean d_i; p from the cluster sign-flip test (10,000 draws, seed 2026), interval from the
cluster bootstrap (10,000 resamples, seed 2026).
  Primary: Delta = R4(bait) - R1(bait).
  D (only if Delta significant, gatekeeping, plan 8.6):
    D_i = [y(R4,bait) - y(R4,correct)] - [y(R1,bait) - y(R0',correct)], same test and interval.
  Claims: both significant and positive -> "better discrimination ... at the observed decision point";
    only Delta significant -> "changed rejection behavior, not changed discrimination".
  Strong context gap (descriptive): Detection(R4) >= 0.70 and Detection(R1) <= 0.30 and D > 0.
  Secondary family, Holm over exactly six p-values, bait version: R2-R1, R3-R1, R4-R2, R5-R4,
    R6(first verdict, outcome 1)-R1, R4n-R4.
  R5 equivalence view (exploratory): bootstrap CI of R5-R4 inside [-0.10, +0.10]; R4-R5 and R4-R1
    reported side by side; no ratio.
  Cut-artifact check (diagnostic): FR(R0') - FR(R0) on correct versions, pairwise, bootstrap CI;
    reference mark <= 0.10.
Descriptive: detection and false rejection per variant; discrimination per variant pair; agreement
between the two draws; detection by episode for R1 and R4; R6 gate outcomes; natural-error N4 - N1 by
error type; bob_states_condition sensitivity (Delta and D on items without the flag); right-reason
share per variant with a seeded hand-check sample of 20 per variant.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.stats import N_DRAWS, SEED, cluster_bootstrap_ci, holm, sign_flip_test

ALPHA = 0.05
SECONDARY = {  # name: (X, Y) with cells (variant, version, outcome)
    "R2-R1": (("R2", "bait", "y"), ("R1", "bait", "y")),
    "R3-R1": (("R3", "bait", "y"), ("R1", "bait", "y")),
    "R4-R2": (("R4", "bait", "y"), ("R2", "bait", "y")),
    "R5-R4": (("R5", "bait", "y"), ("R4", "bait", "y")),
    "R6first-R1": (("R6", "bait", "r6_first_y"), ("R1", "bait", "y")),
    "R4n-R4": (("R4n", "bait", "y"), ("R4", "bait", "y")),
}
EQUIV_MARGIN = 0.10
CUT_MARK = 0.10
STRONG = dict(r4_min=0.70, r1_max=0.30)
VARIANTS = ["R0", "R0p", "R1", "R2", "R3", "R4", "R4n", "R5", "R6"]


# ---------------------------------------------------------------- loading

def _y(verdict, status):
    if status != "ok" or verdict not in ("accept", "reject"):
        return np.nan
    return 1.0 if verdict == "reject" else 0.0


def calls_frame(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        st = r.get("verdict_status")
        row = dict(call_id=r["call_id"], item_id=r["item_id"], variant=r["variant"], version=r["version"],
                   draw=int(r["draw"]), verdict_status=st, verdict=r.get("verdict"), reasoning=r.get("reasoning") or "",
                   y=_y(r.get("verdict"), st))
        r6 = ((r.get("extra") or {}).get("r6")) if r.get("variant") == "R6" else None
        if r6:
            row.update(r6_first_y=_y(r6.get("first_verdict"), "ok" if r6.get("first_verdict") else "missing"),
                       r6_gate_fired=bool(r6.get("gate_fired")),
                       r6_retry_y=_y(r6.get("retry_verdict"), "ok" if r6.get("retry_verdict") else "missing"),
                       r6_final_y=_y(r6.get("final_verdict"), "ok" if r6.get("final_verdict") else "missing"),
                       r6_first_compliant=bool((r6.get("first_check") or {}).get("compliant")),
                       first_reasoning=(r.get("extra") or {}).get("first_reasoning") or "")
        rows.append(row)
    return pd.DataFrame(rows)


def load_calls(results_dir, stage: str = "main", check: str | None = None, mode: str = "live") -> pd.DataFrame:
    from src.runner.costs import iter_call_lines
    recs = [r for r in iter_call_lines(Path(results_dir)) if r.get("stage") == stage and r.get("mode") == mode
            and (check is None or r.get("check") == check)]
    # a resumed run never duplicates call_ids; keep the last line per call_id defensively
    seen = {}
    for r in recs:
        seen[r["call_id"]] = r
    return calls_frame(list(seen.values()))


# ---------------------------------------------------------------- cells and contrasts

def coded(calls: pd.DataFrame, outcome: str, missing: str) -> pd.Series:
    v = calls[outcome] if outcome in calls else pd.Series(np.nan, index=calls.index)
    if missing == "accept":
        return v.fillna(0.0)
    if missing == "reject":
        return v.fillna(1.0)
    return v


def cell(calls: pd.DataFrame, variant: str, version: str, outcome: str = "y", missing: str = "exclude") -> pd.Series:
    sub = calls[(calls.variant == variant) & (calls.version == version)].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    sub["_v"] = coded(sub, outcome, missing)
    return sub.groupby("item_id")["_v"].mean().dropna()


def paired(a: pd.Series, b: pd.Series) -> pd.Series:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    return j["a"] - j["b"]


def test_contrast(d: pd.Series, meta: pd.DataFrame, n_draws=N_DRAWS, seed=SEED) -> dict:
    if len(d) == 0:
        return dict(estimate=None, p=None, ci_low=None, ci_high=None, n_items=0, n_clusters=0)
    cl = meta.loc[d.index, "cluster"].values
    t = sign_flip_test(d.values, cl, n_draws, seed)
    ci = cluster_bootstrap_ci(d.values, cl, n_draws, seed)
    return dict(estimate=t["estimate"], p=t["p"], ci_low=ci["ci_low"], ci_high=ci["ci_high"],
                n_items=t["n_items"], n_clusters=t["n_clusters"])


def D_series(calls, missing="exclude") -> pd.Series:
    r4b, r4c = cell(calls, "R4", "bait", missing=missing), cell(calls, "R4", "correct", missing=missing)
    r1b, r0p = cell(calls, "R1", "bait", missing=missing), cell(calls, "R0p", "correct", missing=missing)
    j = pd.concat([r4b.rename("r4b"), r4c.rename("r4c"), r1b.rename("r1b"), r0p.rename("r0p")], axis=1).dropna()
    return (j.r4b - j.r4c) - (j.r1b - j.r0p)


def primary(calls, meta, missing="exclude", n_draws=N_DRAWS, seed=SEED) -> dict:
    r4b, r1b = cell(calls, "R4", "bait", missing=missing), cell(calls, "R1", "bait", missing=missing)
    delta = test_contrast(paired(r4b, r1b), meta, n_draws, seed)
    out = {"Delta_R4_minus_R1": delta, "detection_R4": float(r4b.mean()) if len(r4b) else None,
           "detection_R1": float(r1b.mean()) if len(r1b) else None}
    sig = delta["p"] is not None and delta["p"] < ALPHA
    if sig:
        out["D"] = test_contrast(D_series(calls, missing), meta, n_draws, seed)
        d_sig = out["D"]["p"] < ALPHA
    else:
        out["D"] = {"tested": False, "reason": "gatekeeping: Delta not significant",
                    "estimate_descriptive": float(D_series(calls, missing).mean()) if len(D_series(calls, missing)) else None}
        d_sig = False
    if sig and d_sig and delta["estimate"] > 0 and out["D"]["estimate"] > 0:
        claim = "better discrimination between correct and bait versions at the observed decision point without the workflow context"
    elif sig:
        claim = "changed rejection behavior, not changed discrimination (criterion shift plausible, not demonstrated)"
    else:
        claim = "no significant Delta"
    out["claim"] = claim
    d_est = out["D"].get("estimate", out["D"].get("estimate_descriptive"))
    out["strong_context_gap"] = bool(out["detection_R4"] is not None and out["detection_R1"] is not None
                                     and out["detection_R4"] >= STRONG["r4_min"] and out["detection_R1"] <= STRONG["r1_max"]
                                     and d_est is not None and d_est > 0)
    return out


def secondary(calls, meta, missing="exclude", n_draws=N_DRAWS, seed=SEED) -> dict:
    res = {}
    for name, ((xv, xs, xo), (yv, ys, yo)) in SECONDARY.items():
        d = paired(cell(calls, xv, xs, xo, missing), cell(calls, yv, ys, yo, missing))
        res[name] = test_contrast(d, meta, n_draws, seed)
    ps = {k: v["p"] for k, v in res.items() if v["p"] is not None}
    adj = holm(ps)
    for k in res:
        res[k]["p_holm"] = adj.get(k)
        res[k]["significant_holm"] = adj.get(k) is not None and adj[k] < ALPHA
    return res


def r5_equivalence(calls, meta, n_draws=N_DRAWS, seed=SEED) -> dict:
    r5, r4, r1 = cell(calls, "R5", "bait"), cell(calls, "R4", "bait"), cell(calls, "R1", "bait")
    r5r4 = test_contrast(paired(r5, r4), meta, n_draws, seed)
    within = r5r4["ci_low"] is not None and r5r4["ci_low"] >= -EQUIV_MARGIN and r5r4["ci_high"] <= EQUIV_MARGIN
    return {"R5-R4": r5r4, "inside_margin": bool(within), "margin": EQUIV_MARGIN,
            "R4-R5": test_contrast(paired(r4, r5), meta, n_draws, seed),
            "R4-R1": test_contrast(paired(r4, r1), meta, n_draws, seed)}


def cut_artifact(calls, meta, n_draws=N_DRAWS, seed=SEED) -> dict:
    d = paired(cell(calls, "R0p", "correct"), cell(calls, "R0", "correct"))
    t = test_contrast(d, meta, n_draws, seed)
    t["mark"] = CUT_MARK
    t["above_mark"] = t["estimate"] is not None and t["estimate"] > CUT_MARK
    return t


# ---------------------------------------------------------------- descriptive

def per_variant(calls) -> pd.DataFrame:
    rows = []
    for v in VARIANTS + ["N1", "N4"]:
        for s in ("bait", "correct"):
            sub = calls[(calls.variant == v) & (calls.version == s)]
            if sub.empty:
                continue
            rows.append(dict(variant=v, version=s, calls=len(sub), missing=int(sub.y.isna().sum()),
                             reject_rate_calls=float(sub.y.mean()) if sub.y.notna().any() else None,
                             items=int(sub.item_id.nunique()),
                             reject_rate_items=float(cell(calls, v, s).mean()) if len(cell(calls, v, s)) else None))
    return pd.DataFrame(rows)


def discrimination(calls, x_bait: str, x_correct: str) -> float | None:
    b, c = cell(calls, x_bait, "bait"), cell(calls, x_correct, "correct")
    if len(b) == 0 or len(c) == 0:
        return None
    return float((1 - c.mean()) - (1 - b.mean()))   # P(ACCEPT | correct) - P(ACCEPT | bait)


def draw_agreement(calls) -> dict:
    out = {}
    for v, s in (("R1", "bait"), ("R0p", "correct"), ("R4", "bait"), ("R4", "correct")):
        sub = calls[(calls.variant == v) & (calls.version == s)].pivot_table(index="item_id", columns="draw", values="y")
        if 1 in sub and 2 in sub:
            both = sub[[1, 2]].dropna()
            out[f"{v}_{s}"] = dict(items=len(both), agreement=float((both[1] == both[2]).mean()) if len(both) else None)
    return out


def r6_gate(calls) -> dict:
    out = {}
    for s in ("bait", "correct"):
        sub = calls[(calls.variant == "R6") & (calls.version == s)]
        if sub.empty or "r6_first_y" not in sub:
            continue
        acc_first = sub[sub.r6_first_y == 0]
        fired = sub[sub.r6_gate_fired.fillna(False).astype(bool)]
        out[s] = dict(calls=len(sub), first_reject_rate=float(sub.r6_first_y.mean()),
                      final_reject_rate=float(sub.r6_final_y.mean()), first_accepts=len(acc_first),
                      first_accept_compliant=int(acc_first.r6_first_compliant.sum()) if len(acc_first) else 0,
                      gate_fired=len(fired), retry_rate=len(fired) / len(acc_first) if len(acc_first) else None,
                      retry_reject=int((fired.r6_retry_y == 1).sum()),
                      gate_reject=int(((fired.r6_final_y == 1) & (fired.r6_retry_y != 1)).sum()),
                      override_rate=float((fired.r6_final_y == 1).mean()) if len(fired) else None)
    out["false_rejection_R6_first_vs_R0p"] = None
    r6c, r0p = cell(calls, "R6", "correct", "r6_first_y"), cell(calls, "R0p", "correct")
    if len(r6c) and len(r0p):
        out["false_rejection_R6_first_vs_R0p"] = dict(R6_first=float(r6c.mean()), R0p=float(r0p.mean()),
                                                      R6_final=float(cell(calls, "R6", "correct", "r6_final_y").mean()))
    return out


def by_episode(calls, meta) -> pd.DataFrame:
    rows = []
    for v in ("R1", "R4"):
        c = cell(calls, v, "bait")
        m = meta.loc[c.index]
        for ep, g in c.groupby(m.episode):
            rows.append(dict(variant=v, episode=int(ep), items=len(g), detection=float(g.mean())))
    return pd.DataFrame(rows)


def natural_errors(calls, nat_meta: pd.DataFrame) -> pd.DataFrame:
    n1, n4 = cell(calls, "N1", "correct"), cell(calls, "N4", "correct")
    j = pd.concat([n1.rename("N1"), n4.rename("N4")], axis=1).join(nat_meta[["task_type", "error_type"]])
    j["error_type"] = j.error_type.fillna(j.task_type)
    g = j.groupby("error_type").agg(items=("N1", "size"), detection_N1=("N1", "mean"), detection_N4=("N4", "mean"))
    g["N4_minus_N1"] = g.detection_N4 - g.detection_N1
    return g.reset_index()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def right_reason(reasoning: str, markers: dict) -> bool:
    """Deterministic string match (plan 8.6; D2 for data search): any marker, case-insensitive and
    whitespace-normalized, is a substring of the reasoning."""
    text = _norm(reasoning)
    return any(_norm(m) and _norm(m) in text for m in markers_list(markers))


def markers_list(markers: dict) -> list[str]:
    out = []
    for k, v in (markers or {}).items():
        if v is None:
            continue
        if k == "violated_threshold" and isinstance(v, str) and "," in v:
            continue   # an IN list's original values are not a violation marker; the added value is used
        out.append(str(v).strip("'"))
    return [m for m in out if m]


def right_reason_table(calls, meta, n_sample: int = 20, seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    rows, samples = [], {}
    rng = np.random.default_rng(seed)
    for v in ("R1", "R2", "R3", "R4", "R4n", "R5", "R6"):
        sub = calls[(calls.variant == v) & (calls.version == "bait") & (calls.y == 1)]
        if v == "R6" and "r6_first_y" in calls:
            sub = calls[(calls.variant == v) & (calls.version == "bait") & (calls.r6_first_y == 1)]
        if sub.empty:
            continue
        text = sub.first_reasoning if (v == "R6" and "first_reasoning" in sub) else sub.reasoning
        rr = [right_reason(t, meta.loc[i, "markers"]) for t, i in zip(text, sub.item_id)]
        rows.append(dict(variant=v, bait_rejects=len(sub), right_reason=int(sum(rr)), share=float(np.mean(rr))))
        k = min(n_sample, len(sub))
        samples[v] = sorted(sub.call_id.values[rng.choice(len(sub), size=k, replace=False)].tolist())
    return pd.DataFrame(rows), samples


# ---------------------------------------------------------------- everything

def analyze(calls: pd.DataFrame, meta: pd.DataFrame, nat_meta: pd.DataFrame | None = None,
            n_draws: int = N_DRAWS, seed: int = SEED) -> dict:
    main_ids = set(meta.index)
    core = calls[calls.item_id.isin(main_ids)]
    res = {"n_main_items": len(main_ids), "n_clusters": int(meta.cluster.nunique())}
    res["primary"] = primary(core, meta, "exclude", n_draws, seed)
    res["secondary"] = secondary(core, meta, "exclude", n_draws, seed)
    res["missing_sensitivity"] = {m: {"primary": primary(core, meta, m, n_draws, seed),
                                      "secondary": secondary(core, meta, m, n_draws, seed)} for m in ("accept", "reject")}
    res["r5_equivalence"] = r5_equivalence(core, meta, n_draws, seed)
    res["cut_artifact"] = cut_artifact(core, meta, n_draws, seed)
    unflag = meta[~meta.bob_states_condition.fillna(False).astype(bool)].index
    res["bob_states_condition_sensitivity"] = {
        "n_items": len(unflag),
        "primary": primary(core[core.item_id.isin(unflag)], meta.loc[unflag], "exclude", n_draws, seed) if len(unflag) else None}
    res["per_variant"] = per_variant(core).to_dict("records")
    res["discrimination"] = {f"{x}|{y}": discrimination(core, x, y) for x, y in
                             [("R1", "R0p"), ("R2", "R2"), ("R3", "R3"), ("R4", "R4"), ("R4n", "R4n"), ("R5", "R5"), ("R6", "R6")]}
    res["draw_agreement"] = draw_agreement(core)
    res["r6_gate"] = r6_gate(core)
    res["by_episode"] = by_episode(core, meta).to_dict("records")
    rr, samples = right_reason_table(core, meta, seed=seed)
    res["right_reason"] = rr.to_dict("records")
    res["right_reason_hand_check_sample"] = samples
    if nat_meta is not None:
        res["natural_errors"] = natural_errors(calls, nat_meta).to_dict("records")
    return res


def to_json(res: dict) -> str:
    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.bool_):
            return bool(o)
        raise TypeError(type(o))
    return json.dumps(res, indent=1, default=conv)
