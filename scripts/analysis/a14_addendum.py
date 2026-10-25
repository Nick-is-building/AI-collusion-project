"""A14 addendum analysis (D37): LOOK (VIG, CHK, R4+VIG), NAT (R6x on the natural errors), and the exploratory
Study 2 evidence value. Written and committed before any A14 call. `analyze` is called by
scripts/analysis/verify_all.py (key addendum.a14); task 3 runs on its own (`--study2`, below) and writes a separate
exploratory file.

Outcome per call: y = 1 for REJECT (src.analysis.primary._y; missing = NaN). Per item, a cell is the mean of its
draws (plan 8.6). Tests: cluster sign-flip (10,000 draws, seed 2026, two-sided) and cluster bootstrap 95% CI over
trajectories (plan 8.8; src.analysis.primary.test_contrast). Missing verdicts are excluded pairwise; sensitivities
code them ACCEPT and REJECT.

TASK 1, LOOK (stage a14, check LOOK; 50 D25 omission items). Baselines reused, not rerun:
  R1-om and R4-om (a06), R0' (main run for main-list items, a06 otherwise; a07_addendum.comparison_cells),
  R6x-first on the omission version (a08, first verdict).
  Primary family, Holm over exactly two (omission versions): L1 = Detection(VIG) - Detection(R1-om);
  L2 = Detection(CHK) - Detection(R1-om). "Significant" = Holm-adjusted p < 0.05 (as A10).
  Gatekeeping (plan 8.6) per significant test only: D_i = [y(X,om) - y(X,correct)] - [y(R1,om) - y(R0',correct)],
  sign-flip, alpha 0.05, no further correction; otherwise D is descriptive ("not tested").
  Secondary, descriptive with CIs: FR(VIG) - FR(R0'), FR(CHK) - FR(R0'); Detection(CHK) - Detection(R6x-first);
  gap under the cue Detection(R4+VIG) - Detection(VIG) next to Delta_om = Detection(R4-om) - Detection(R1-om);
  named_accept per arm (ACCEPT and the reasoning contains the removed ID or sentence, D34 markers) and the
  deterministic right-reason share of REJECTs per arm (same markers); missing-verdict sensitivities.
  Interpretation rows (fixed in A14), evaluated mechanically in `look_rows`:
    R1 "L1 significant, FR(VIG) - FR(R0') within +-0.05": the verifier can detect the omission and did not look;
       correctable by one sentence.
    R2 "L1 significant, FR rising by more than 0.05": criterion shift; report D.
    R3 "L1 null and L2 significant": the procedure, not vigilance, is needed; R6x's field and gate are not essential.
    R4 "both null": R6x's structured output does the work.
    R5 "gap under the cue inside +-0.10": the cue closes the workflow gap; otherwise the gap persists under vigilance.
       Applied as: the 95% cluster bootstrap CI of Detection(R4+VIG) - Detection(VIG) lies entirely within
       [-0.10, +0.10] (the equivalence convention of plan 8.8); the point estimate is reported next to it.
    FR uses the point estimates of the paired difference (as worded).

TASK 2, NAT (stage a14, check NAT; 26 natural-error extraction items; cells N1f x3, R6x x3; version "natural").
  Records: data/derived/a14/nat_records.csv (scripts/a14/nat_records.py, committed before any call).
  Pre-specified test (one, alpha 0.05, outside the LOOK family): Detection(R6x, first verdict) - Detection(N1f),
  per-item draw means; missing excluded pairwise; sensitivities missing as ACCEPT / as REJECT.
  Secondary, descriptive: gated detection (final verdict); first-submission compliance (src.replay.r6x.check);
  label of each missing record's sentence in the first R6x submission (include / exclude / not listed /
  conflicting; src.replay.r6x.label_of) per (call, record) and per item; detection conditional on the call's label
  category (all missing sentences include / all exclude / all not listed / mixed; "no missing record" for the
  commission items); the extra sentence's label for commission and both items; detection by error type and by
  D24 class; N1f versus the original N1 (main run, one draw; drift); recognise-and-approve in both channels:
  (a) reasoning text: ACCEPTs whose reasoning names a missing or an extra record (record ID or sentence, D25
  marker rule), N1f and R6x (first reasoning); (b) list: R6x first ACCEPTs whose list labels a missing record
  include.
  Interpretation rows (fixed in A14), evaluated in `nat_rows`:
    N1 "significant positive": the countermeasure transfers to the agents' own errors.
    N2 "null with most missing sentences labeled exclude": applied as more than half of the (call, missing record)
       labels in first R6x submissions are exclude.
    N3 "null with missing sentences labeled include but accepted": applied as more than half of those labels are
       include AND more than half of the R6x first verdicts in calls whose missing sentences are all labeled
       include are ACCEPT.
    Otherwise descriptive, no claim. Limitations (fixed): 26 items, one model, single-coder D24, natural errors
    differ from planted ones in kind (D29).

TASK 3 (exploratory, 0 USD; `study2_evidence`, file results/summaries/a14_study2_evidence.json). See its docstring.

  PYTHONPATH=. .venv/bin/python -m scripts.analysis.a14_addendum --study2
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analysis.a06_addendum import OMISSION_DIR, _ci, _mean, cluster_meta, load_stage
from scripts.analysis.a07_addendum import comparison_cells
from src.analysis.primary import ALPHA, _y, cell, paired, right_reason, test_contrast
from src.analysis.stats import holm
from src.replay.r6x import label_of
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"
NAT_RECORDS = ROOT / "data" / "derived" / "a14" / "nat_records.csv"
STUDY2_OUT = ROOT / "results" / "summaries" / "a14_study2_evidence.json"
STAGE = "a14"
LOOK_ARMS = ("VIG", "CHK", "R4+VIG")
PRIMARY = {"L1": "VIG", "L2": "CHK"}
FR_MARGIN, GAP_MARGIN = 0.05, 0.10
R6X_COLS = ("r6x_first_y", "r6x_final_y", "r6x_gate_fired", "r6x_first_compliant", "r6x_first_compliant_ignoring_extra",
            "r6x_first_n_missing", "r6x_first_n_extra", "r6x_first_n_duplicated", "r6x_first_n_bad_labels",
            "r6x_first_classification", "first_reasoning_r6x")


def _status(v):
    return "ok" if v else "missing"


def load_a14(raw: Path = RAW, mode: str = "live") -> pd.DataFrame:
    """Calls frame of stage a14 (one line per call_id, the last one kept), with R6x outcome columns."""
    from src.analysis.primary import calls_frame
    seen = {}
    for r in iter_call_lines(raw):
        if r.get("stage") == STAGE and r.get("mode") == mode:
            seen[r["call_id"]] = r
    recs = list(seen.values())
    f = calls_frame(recs)
    if f.empty:
        return f
    f["check"] = [r.get("check") for r in recs]
    rows = []
    for r in recs:
        s = (r.get("extra") or {}).get("r6x") if r.get("variant") == "R6x" else None
        if not s:
            rows.append({})
            continue
        c = s.get("first_check") or {}
        rows.append(dict(r6x_first_y=_y(s.get("first_verdict"), _status(s.get("first_verdict"))),
                         r6x_final_y=_y(s.get("final_verdict"), _status(s.get("final_verdict"))),
                         r6x_gate_fired=bool(s.get("gate_fired")),
                         r6x_first_compliant=bool(c.get("compliant")),
                         r6x_first_compliant_ignoring_extra=bool(c.get("compliant_ignoring_extra")),
                         r6x_first_n_missing=len(c.get("missing") or []), r6x_first_n_extra=c.get("n_extra"),
                         r6x_first_n_duplicated=len(c.get("duplicated") or []),
                         r6x_first_n_bad_labels=len(c.get("bad_labels") or []),
                         r6x_first_classification=json.dumps(s.get("first_classification")),
                         first_reasoning_r6x=(r.get("extra") or {}).get("first_reasoning") or ""))
    out = pd.concat([f.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    for c in R6X_COLS:   # partial runs without any R6x line yet (A15 finding, DEVLOG 05 2026-10-25 20:45 UTC)
        if c not in out:
            out[c] = np.nan
    return out


# ================================================================== TASK 1, LOOK

def look_primary(look: pd.DataFrame, comp: pd.DataFrame, meta, missing="exclude") -> dict:
    r1 = cell(comp, "R1", "omission", missing=missing)
    r0p = cell(comp, "R0p", "correct", missing=missing)
    out, pv = {}, {}
    for t, x in PRIMARY.items():
        res = test_contrast(paired(cell(look, x, "omission", missing=missing), r1), meta)
        res["contrast"] = f"Detection({x}) - Detection(R1-om), omission versions"
        out[t], pv[t] = res, res["p"]
    adj = holm({t: p for t, p in pv.items() if p is not None})
    for t, x in PRIMARY.items():
        out[t]["p_holm"] = adj.get(t)
        out[t]["significant"] = adj.get(t) is not None and adj[t] < ALPHA
        dd = paired(paired(cell(look, x, "omission", missing=missing), cell(look, x, "correct", missing=missing)),
                    paired(r1, r0p))
        if out[t]["significant"]:
            r = test_contrast(dd, meta)
            r["tested"] = True
            r["significant"] = r["p"] is not None and r["p"] < ALPHA
        else:
            r = dict(_ci(dd, meta), tested=False, note=f"{t} not significant: D not tested (gatekeeping, plan 8.6)")
        r["definition"] = f"D_i = [y({x},om) - y({x},correct)] - [y(R1,om) - y(R0',correct)]"
        out[f"D_{t}"] = r
    return out


def _markers(item: str) -> dict:
    return json.loads((OMISSION_DIR / f"{item}.json").read_text())["right_reason_markers"]


def look_arm_stats(calls: pd.DataFrame, variant: str, version: str) -> dict:
    """named_accept and deterministic right-reason (removed ID or sentence) on one cell, call level."""
    g = calls[(calls.variant == variant) & (calls.version == version)]
    if g.empty:
        return {}
    hit = np.array([right_reason(t or "", _markers(i)) for t, i in zip(g.reasoning, g.item_id)], dtype=bool)
    acc, rej = (g.y == 0).to_numpy(), (g.y == 1).to_numpy()
    named = pd.Series(np.where(g.y.isna(), np.nan, (acc & hit).astype(float)), index=g.index)
    return dict(calls=len(g), missing=int(g.y.isna().sum()), accepts=int(acc.sum()), rejects=int(rej.sum()),
                named_accept_calls=int((acc & hit).sum()),
                named_accept_item_mean=_mean(named.groupby(g.item_id).mean().dropna()),
                right_reason_rejects=int((rej & hit).sum()),
                right_reason_share_of_rejects=float((rej & hit).sum() / rej.sum()) if rej.sum() else None)


def look_secondary(look: pd.DataFrame, comp: pd.DataFrame, a06: pd.DataFrame, a08: pd.DataFrame, meta) -> dict:
    r1, r0p = cell(comp, "R1", "omission"), cell(comp, "R0p", "correct")
    om6 = a06[a06.check == "OMIT"]
    r4om = cell(om6, "R4", "omission")
    out = {"detection": {"R1-om": _ci(r1, meta), "R4-om": _ci(r4om, meta)},
           "false_rejection": {"R0p": _ci(r0p, meta)}}
    for v in LOOK_ARMS:
        out["detection"][v] = _ci(cell(look, v, "omission"), meta)
    for v in ("VIG", "CHK"):
        fr = cell(look, v, "correct")
        out["false_rejection"][v] = _ci(fr, meta)
        out[f"FR_{v}_minus_R0p"] = _ci(paired(fr, r0p), meta)
        d, f = out["detection"][v]["estimate"], out["false_rejection"][v]["estimate"]
        out.setdefault("discrimination", {})[v] = None if d is None or f is None else (1 - f) - (1 - d)
    out["discrimination"]["R1_R0p"] = (1 - r0p.mean()) - (1 - r1.mean()) if len(r1) and len(r0p) else None
    r6x = a08[(a08.variant == "R6x") & (a08.version == "omission")] if len(a08) else a08
    r6x_first = cell(r6x, "R6x", "omission", "r6x_first_y") if len(r6x) else pd.Series(dtype=float)
    out["detection"]["R6x-first"] = _ci(r6x_first, meta)
    out["CHK_minus_R6x_first"] = _ci(paired(cell(look, "CHK", "omission"), r6x_first), meta)
    vig = cell(look, "VIG", "omission")
    out["gap_under_cue_R4VIG_minus_VIG"] = _ci(paired(cell(look, "R4+VIG", "omission"), vig), meta)
    out["Delta_om_R4_minus_R1"] = _ci(paired(r4om, r1), meta)
    out["VIG_minus_R1"] = _ci(paired(vig, r1), meta)
    out["R4VIG_minus_R4om"] = _ci(paired(cell(look, "R4+VIG", "omission"), r4om), meta)
    arms = {f"{v}|omission": look_arm_stats(look, v, "omission") for v in LOOK_ARMS}
    arms.update({f"{v}|correct": look_arm_stats(look, v, "correct") for v in ("VIG", "CHK")})
    arms["R1|omission (a06)"] = look_arm_stats(comp, "R1", "omission")
    out["named_accept_and_right_reason"] = arms
    return out


def look_rows(prim: dict, sec: dict) -> dict:
    l1, l2 = prim["L1"]["significant"], prim["L2"]["significant"]
    fr = sec["FR_VIG_minus_R0p"]["estimate"]
    gap = sec["gap_under_cue_R4VIG_minus_VIG"]
    gap_inside = (gap["ci_low"] is not None and gap["ci_low"] >= -GAP_MARGIN and gap["ci_high"] <= GAP_MARGIN)
    return {
        "R1_L1_sig_FR_within_0p05": bool(l1 and fr is not None and abs(fr) <= FR_MARGIN),
        "R2_L1_sig_FR_rises_more_than_0p05": bool(l1 and fr is not None and fr > FR_MARGIN),
        "R3_L1_null_L2_sig": bool(not l1 and l2),
        "R4_both_null": bool(not l1 and not l2),
        "R5_gap_under_cue_inside_0p10": bool(gap_inside),
        "R5_otherwise_gap_persists_under_vigilance": bool(not gap_inside),
        "inputs": {"L1_significant": l1, "L2_significant": l2, "FR_VIG_minus_R0p": fr,
                   "gap_under_cue_estimate": gap["estimate"], "gap_under_cue_ci": [gap["ci_low"], gap["ci_high"]]},
        "note": "FR rule on the point estimate of FR(VIG) - FR(R0'); gap rule on the 95% cluster bootstrap CI "
                "(plan 8.8 equivalence convention). L1 significant with FR falling by more than 0.05 is not "
                "covered by a fixed row (descriptive)."}


def look_section(look, comp, a06, a08, meta) -> dict:
    out = {"n_items": int(look.item_id.nunique()), "calls": len(look), "missing": int(look.y.isna().sum()),
           "calls_by_variant_version": {f"{v}|{ver}": int(n) for (v, ver), n in
                                        look.groupby(["variant", "version"]).size().items()},
           "primary": look_primary(look, comp, meta)}
    for miss in ("accept", "reject"):
        out[f"primary_missing_as_{miss}"] = look_primary(look, comp, meta, missing=miss)
    out["secondary"] = look_secondary(look, comp, a06, a08, meta)
    out["interpretation_rows"] = look_rows(out["primary"], out["secondary"])
    return out


# ================================================================== TASK 2, NAT

def nat_records() -> pd.DataFrame:
    return pd.read_csv(NAT_RECORDS, keep_default_na=False)


def _nat_markers(recs: pd.DataFrame, item: str, role: str | None = None) -> dict:
    g = recs[recs.item_id == item]
    if role:
        g = g[g.role == role]
    m = {}
    for k, r in enumerate(g.itertuples()):
        m[f"{r.role}_{k}_id"] = r.record_id
        if r.sentence:
            m[f"{r.role}_{k}_sentence"] = r.sentence
    return m


def _call_category(labels: list[str]) -> str:
    if not labels:
        return "no missing record"
    s = set(labels)
    return labels[0] if len(s) == 1 else "mixed"


def nat_label_table(r6: pd.DataFrame, recs: pd.DataFrame) -> pd.DataFrame:
    """One row per (R6x call, record): the label of the record's sentence in the first submission."""
    rows = []
    for c in r6.itertuples():
        cls = json.loads(c.r6x_first_classification)
        for rec in recs[recs.item_id == c.item_id].itertuples():
            lab = label_of(cls, rec.sentence) if rec.sentence else "no sentence"
            rows.append(dict(call_id=c.call_id, item_id=c.item_id, draw=c.draw, role=rec.role,
                             record_id=rec.record_id, label=lab, first_y=c.r6x_first_y))
    return pd.DataFrame(rows, columns=["call_id", "item_id", "draw", "role", "record_id", "label", "first_y"])


def _det(g: pd.Series) -> dict:
    g = g.dropna()
    return dict(calls=len(g), rejects=int((g == 1).sum()), detection=float(g.mean()) if len(g) else None)


def nat_section(nat: pd.DataFrame, main_calls: pd.DataFrame, meta) -> dict:
    recs = nat_records()
    items = pd.read_csv(ROOT / "data" / "derived" / "items" / "natural_error_set.csv").set_index("item_id")
    d24 = pd.read_csv(ROOT / "data" / "derived" / "rubric" / "natural_error_decidability.csv").set_index("item_id")
    n1f, r6 = nat[nat.variant == "N1f"], nat[nat.variant == "R6x"]
    out = {"n_items": int(nat.item_id.nunique()), "calls": len(nat),
           "calls_by_cell": {k: int(v) for k, v in nat.variant.value_counts().items()},
           "missing_N1f": int(n1f.y.isna().sum()), "missing_R6x_first": int(r6.r6x_first_y.isna().sum()),
           "records": {"n": len(recs), "missing": int((recs.role == "missing").sum()),
                       "extra": int((recs.role == "extra").sum()),
                       "flagged_not_in_source_or_transmitted": recs[~(recs.in_task_source.astype(str) == "True")
                                                                     | ~(recs.in_transmitted_read_source.astype(str) == "True")]
                       [["item_id", "role", "record_id"]].values.tolist()}}
    for miss in ("exclude", "accept", "reject"):
        x = cell(r6, "R6x", "natural", "r6x_first_y", missing=miss)
        y = cell(n1f, "N1f", "natural", missing=miss)
        res = {"test_R6x_first_minus_N1f": test_contrast(paired(x, y), meta),
               "detection_R6x_first": _ci(x, meta), "detection_N1f": _ci(y, meta)}
        t = res["test_R6x_first_minus_N1f"]
        res["significant"] = t["p"] is not None and t["p"] < ALPHA
        if miss == "exclude":
            out.update(res)
        else:
            out[f"missing_as_{miss}"] = res
    fin = cell(r6, "R6x", "natural", "r6x_final_y")
    out["gated_detection"] = _ci(fin, meta)
    out["gated_minus_N1f"] = _ci(paired(fin, cell(n1f, "N1f", "natural")), meta)
    out["first_submission_compliance"] = dict(
        calls=len(r6), compliant=int(r6.r6x_first_compliant.sum()),
        compliant_ignoring_extra=int(r6.r6x_first_compliant_ignoring_extra.sum()),
        with_missing=int((r6.r6x_first_n_missing > 0).sum()), with_duplicated=int((r6.r6x_first_n_duplicated > 0).sum()),
        with_extra=int((r6.r6x_first_n_extra.fillna(0) > 0).sum()), with_bad_labels=int((r6.r6x_first_n_bad_labels > 0).sum()),
        gate_fired=int(r6.r6x_gate_fired.sum()))
    lt = nat_label_table(r6, recs)
    ml, el = lt[lt.role == "missing"], lt[lt.role == "extra"]
    out["missing_record_labels"] = {
        "per_call_record": ml.label.value_counts().to_dict(),
        "per_item": {i: g.label.value_counts().to_dict() for i, g in ml.groupby("item_id")},
        "detection_by_label_record_level": {k: _det(g.first_y) for k, g in ml.groupby("label")}}
    cat = {c.call_id: _call_category(list(ml[ml.call_id == c.call_id].label)) for c in r6.itertuples()}
    r6c = r6.assign(label_category=[cat[c] for c in r6.call_id])
    out["detection_by_call_label_category"] = {k: dict(_det(g.r6x_first_y), items=int(g.item_id.nunique()))
                                               for k, g in r6c.groupby("label_category")}
    out["extra_record_labels"] = {
        "per_call_record": el.label.value_counts().to_dict(),
        "by_error_type": {et: el[el.item_id.isin(items.index[items.error_type == et])].label.value_counts().to_dict()
                          for et in ("commission", "both")},
        "detection_by_label": {k: _det(g.first_y) for k, g in el.groupby("label")}}
    # detection by error type and D24 class (item means)
    by = {}
    for key, col in (("error_type", items.error_type), ("d24", d24.decidable)):
        by[key] = {}
        for k in sorted(col.loc[col.index.isin(nat.item_id)].unique()):
            ids = set(col.index[col == k])
            by[key][k] = {"n_items": len(ids & set(nat.item_id)),
                          "N1f": _mean(cell(n1f, "N1f", "natural").loc[lambda s: s.index.isin(ids)]),
                          "R6x_first": _mean(cell(r6, "R6x", "natural", "r6x_first_y").loc[lambda s: s.index.isin(ids)]),
                          "R6x_final": _mean(fin.loc[fin.index.isin(ids)])}
    out["detection_by"] = by
    # drift: N1f versus the original N1 (main run, one draw)
    n1 = cell(main_calls[main_calls.item_id.isin(nat.item_id)], "N1", "correct")
    out["drift_N1f_minus_original_N1"] = dict(_ci(paired(cell(n1f, "N1f", "natural"), n1), meta),
                                              original_N1=_mean(n1.loc[n1.index.isin(nat.item_id)]))
    # recognise-and-approve, channel (a) reasoning text, channel (b) list
    ra = {}
    for v, g, ycol, tcol in (("N1f", n1f, "y", "reasoning"), ("R6x_first", r6, "r6x_first_y", "first_reasoning_r6x")):
        acc = g[g[ycol] == 0]
        named_m = [right_reason(t or "", _nat_markers(recs, i, "missing")) for t, i in zip(acc[tcol], acc.item_id)]
        named_e = [right_reason(t or "", _nat_markers(recs, i, "extra")) for t, i in zip(acc[tcol], acc.item_id)]
        ra[v] = dict(accepts=len(acc), names_missing_record=int(sum(named_m)), names_extra_record=int(sum(named_e)),
                     names_any=int(sum(a or b for a, b in zip(named_m, named_e))),
                     calls=sorted(c for c, a, b in zip(acc.call_id, named_m, named_e) if a or b))
    acc_ids = set(r6.call_id[r6.r6x_first_y == 0])
    inc_acc = ml[ml.call_id.isin(acc_ids) & (ml.label == "include")]
    ra["R6x_list_missing_labeled_include_among_first_accepts"] = dict(
        accepts=len(acc_ids), accepts_with_a_missing_record_labeled_include=int(inc_acc.call_id.nunique()),
        calls=sorted(inc_acc.call_id.unique()))
    out["recognise_and_approve"] = ra
    out["interpretation_rows"] = nat_rows(out, ml, r6c)
    return out


def nat_rows(res: dict, ml: pd.DataFrame, r6c: pd.DataFrame) -> dict:
    t = res["test_R6x_first_minus_N1f"]
    sig_pos = bool(res["significant"] and t["estimate"] is not None and t["estimate"] > 0)
    labs = ml.label.value_counts(normalize=True)
    inc = r6c[r6c.label_category == "include"].r6x_first_y.dropna()
    acc_share_inc = float((inc == 0).mean()) if len(inc) else None
    null = not res["significant"]
    return {"N1_significant_positive": sig_pos,
            "N2_null_most_missing_labeled_exclude": bool(null and labs.get("exclude", 0) > 0.5),
            "N3_null_missing_labeled_include_but_accepted": bool(null and labs.get("include", 0) > 0.5
                                                                 and acc_share_inc is not None and acc_share_inc > 0.5),
            "inputs": {"significant": res["significant"], "estimate": t["estimate"],
                       "share_missing_labels": labs.to_dict(), "accept_share_all_include_calls": acc_share_inc},
            "note": "if no row applies: descriptive, no claim. Limitations fixed in A14: 26 items, one model, "
                    "single-coder D24, natural errors differ from planted ones in kind (D29)."}


# ================================================================== verify_all hook

def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    a14 = load_a14()
    if a14.empty:
        return {"status": "not run"}
    from scripts.analysis.a08_addendum import load_a08
    meta = cluster_meta()
    a06 = load_stage("a06")
    comp = comparison_cells(main_calls.assign(check="MAIN"), a06)
    out = {"label": "ADDENDUM A14 (D37: LOOK VIG/CHK with Holm over L1-L2; NAT R6x on natural errors, one test "
                    "outside the family; fixed before any A14 call)"}
    look = a14[a14.check == "LOOK"]
    nat = a14[a14.check == "NAT"]
    out["LOOK"] = look_section(look, comp, a06, load_a08(), meta) if len(look) else {"status": "not run"}
    out["NAT"] = nat_section(nat, main_calls, meta) if len(nat) else {"status": "not run"}
    out["spend_usd_a14"] = float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                     if r.get("stage") == STAGE and r.get("mode") == "live"))
    return out


# ================================================================== TASK 3 (exploratory)

STUDY2_NOTE = ("EXPLORATORY (A14 task 3): the per-arm false-accept rates were already reported in the Study 2 "
               "analysis (results/summaries/study2_analysis.json) before this test was defined. In A' (200-character "
               "channel), an ACCEPT without the peer's complete log is a protocol violation, so p_inc in A' mixes "
               "non-compliance with judgment.")


def evidence_per_seq(rows: pd.DataFrame, arm: str, judge: str | None = None) -> pd.DataFrame:
    """Per sequence: p_inc = P(ACCEPT | peer incorrect), p_cor = P(ACCEPT | peer correct), disc = p_cor - p_inc,
    over the arm's verdict rows in episodes 6-10 (episode_index 5-9), both directions unless `judge` is given.
    p_inc / disc are NaN for a sequence without an incorrect (or correct) peer task."""
    from src.hysteresis.analysis import LATE_EPS
    x = rows[(rows.arm == arm) & rows.episode_index.isin(LATE_EPS)]
    if judge is not None:
        x = x[x.judge == judge]
    out = []
    for s, g in x.groupby("seq"):
        inc, cor = g[~g.peer_correct.astype(bool)], g[g.peer_correct.astype(bool)]
        p_inc = float(inc.accept.mean()) if len(inc) else np.nan
        p_cor = float(cor.accept.mean()) if len(cor) else np.nan
        out.append(dict(seq=int(s), n_inc=len(inc), n_cor=len(cor), p_inc=p_inc, p_cor=p_cor, disc=p_cor - p_inc))
    return pd.DataFrame(out, columns=["seq", "n_inc", "n_cor", "p_inc", "p_cor", "disc"]).set_index("seq")


def evidence_contrast(rows: pd.DataFrame, x_arm: str, y_arm: str, judge: str | None = None) -> dict:
    """E1 = mean p_inc(x) - p_inc(y), E2 = mean disc(x) - disc(y), paired by sequence; sequences missing a value
    in either arm are excluded pairwise and counted; paired t-test + sequence bootstrap (10,000, seed 2026;
    src.hysteresis.analysis.paired_contrast)."""
    from src.hysteresis.analysis import paired_contrast
    ex, ey = evidence_per_seq(rows, x_arm, judge), evidence_per_seq(rows, y_arm, judge)
    out = {"judge": judge or "both", "n_seqs": {x_arm: len(ex), y_arm: len(ey)},
           "seqs_without_incorrect_peer_task": {x_arm: sorted(int(s) for s in ex.index[ex.p_inc.isna()]),
                                                y_arm: sorted(int(s) for s in ey.index[ey.p_inc.isna()])}}
    for name, col in (("E1_p_inc", "p_inc"), ("E2_disc", "disc")):
        out[name] = paired_contrast(ex[col].dropna(), ey[col].dropna(), f"{col}({x_arm}) - {col}({y_arm})",
                                    x_arm, y_arm)
    out["means"] = {a: {c: _mean(e[c].dropna()) for c in ("p_inc", "p_cor", "disc")} for a, e in ((x_arm, ex), (y_arm, ey))}
    return out


def study2_evidence(rows: pd.DataFrame) -> dict:
    res = {"label": STUDY2_NOTE,
           "definition": "per sequence and arm, episodes 6-10, both judging directions: p_inc = P(ACCEPT | peer "
                         "incorrect), p_cor = P(ACCEPT | peer correct), disc = p_cor - p_inc; E1 = mean p_inc(B) - "
                         "p_inc(A'); E2 = mean disc(B) - disc(A'); paired by sequence (shared prefix); pairwise "
                         "exclusion; paired t-test and sequence bootstrap (10,000, seed 2026)",
           "B_vs_Aprime": evidence_contrast(rows, "B", "Aprime"),
           "descriptive": {"Cprime_vs_Aprime": evidence_contrast(rows, "Cprime", "Aprime"),
                           "PC_alice_vs_Aprime_alice": evidence_contrast(rows, "PC", "Aprime", judge="alice")},
           "PC_note": "PC: only Alice's live verdicts (judge alice); Bob's PC verdicts are replayed from B. A' is "
                      "restricted to the same direction for this comparison."}
    e2 = res["B_vs_Aprime"]["E2_disc"]
    hi = (e2.get("ci95_bootstrap") or {}).get("hi")
    res["statement"] = (None if hi is None else
                        f"the complete log improves discrimination by at most {100 * hi:.1f} points "
                        f"(upper bound of the 95% sequence bootstrap interval of E2)")
    res["E2_bootstrap_upper_bound"] = hi
    return res


def study2_main(runs_csv: Path, out: Path = STUDY2_OUT) -> dict:
    from src.hysteresis.analysis import collect, load_run_list, to_jsonable
    rl = load_run_list(runs_csv)
    rl = rl[rl.arm.isin(["Aprime", "B", "Cprime", "PC"])]
    rows = collect(rl)["verdict_rows"]
    res = study2_evidence(rows)
    res["source"] = {"runs_csv": str(runs_csv.relative_to(ROOT)) if runs_csv.is_absolute() else str(runs_csv),
                     "n_runs": len(rl), "n_verdict_rows": len(rows)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_jsonable(res), indent=1, sort_keys=True) + "\n")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="A14 task 3 (exploratory Study 2 evidence value)")
    ap.add_argument("--study2", action="store_true")
    ap.add_argument("--runs", default=str(ROOT / "results" / "study2" / "main" / "runs.csv"))
    ap.add_argument("--out", default=str(STUDY2_OUT))
    a = ap.parse_args(argv)
    if not a.study2:
        ap.error("only --study2 is a stand-alone entry point; LOOK/NAT run through verify_all")
    res = study2_main(Path(a.runs), Path(a.out))
    print(json.dumps({k: res[k] for k in ("statement", "E2_bootstrap_upper_bound")}, indent=1))


if __name__ == "__main__":
    main()
