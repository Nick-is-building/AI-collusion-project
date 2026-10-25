"""A16 addendum analysis (D39): Gemini 3.8 Flash judging in Gemini 3.1 Flash-Lite's trajectories, on the identical
D25 contexts (exploratory transfer study); called by scripts/analysis/verify_all.py (key addendum.a16). Written and
committed before any A16 call.

Cells (per item a cell is the mean of its draws, y = 1 for REJECT; plan 8.6), stage a16, check XVER:
  omission: R1, R4, R2, R1+CHK;  correct: R0p (= R0'), R4, R2, R1+CHK;  bait: R1 (= R1-com, 22 shared items, 1 draw).
Flash-Lite comparison cells (reused, never rerun; same items and contexts): R1/R4 omission (a06), R0'/R4 correct (main
run for main-list items, a06 otherwise), R2 (A13), CHK (A14, labeled R1+CHK here), R1 bait (main run).

Primary item set: the 50 D25 items minus rep041_e06 (pre-specified) and rep044_e03 (second genuine residue found by the
D40 scan; Nick's decision, D39, before any A16 call). Sensitivities: all 50 items; without all 4 D40-flagged items. The exclusions are frozen in
EXCLUSIONS (written by `--freeze-exclusions` from the committed D40 file data/derived/residue_scan_d25.csv, column
`flagged`; it reads no A16 outcome); until that file exists, `analyze` returns
status "awaiting exclusion freeze" and reads no A16 outcome.
Primary family (Holm over exactly three; omission versions; cluster sign-flip over trajectories 10,000 and cluster
bootstrap 95% 10,000, seed 2026, two-sided):
  G = Detection(R4) - Detection(R1);  H = Detection(R2) - Detection(R1);  C = Detection(R1+CHK) - Detection(R1).
  "Significant" = Holm-adjusted p < 0.05. Gatekeeping per significant contrast (plan 8.6):
  D_i = [y(X,om) - y(X,correct)] - [y(R1,om) - y(R0',correct)]; otherwise D descriptive.
Verifier comparison (descriptive, paired by item, cluster bootstrap CI, no test): every cell, 3.8 Flash minus
  Flash-Lite; per-item contrasts G, H, C, 3.8 Flash minus Flash-Lite.
Secondary (descriptive): false rejection per cell and FR(X) - FR(R0'); equivalence flags (CI inside +-0.10); R1-com
  detection; named_accept and deterministic right-reason (D25 markers; main-run bait markers for R1-com); draw agreement;
  missing-verdict sensitivities (missing coded ACCEPT / REJECT); everything also on the two sensitivity item sets.
Interpretation rows (A16, applied literally; evaluated on the primary item set, missing excluded).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

import pandas as pd

from scripts.analysis.a06_addendum import RAW, _ci, cluster_meta, load_stage
from scripts.analysis.a13_addendum import baseline_cells, items_info
from src.analysis.primary import ALPHA, EQUIV_MARGIN, cell, paired, right_reason, test_contrast
from src.analysis.stats import holm
from src.replay import a16
from src.runner.costs import iter_call_lines
from src.runner.runner import normalize_model

ROOT = Path(__file__).resolve().parents[2]
STAGE = "a16"
EXCLUSIONS = ROOT / "data" / "derived" / "a16" / "primary_exclusions.json"
D40_SCAN = ROOT / "data" / "derived" / "residue_scan_d25.csv"   # D40 residue scan (column `flagged`)
PRESPECIFIED_EXCLUSION = "rep041_e06_alice"
# Nick's decision (D39, 25 Oct 2026, before any A16 call): of the 4 D40-flagged items, only the 2 genuine residues are
# excluded from the primary analysis; rep018_e02 and rep029_e09 are rule hits on a phrase shared with another record.
PRIMARY_EXCLUSIONS = ("rep041_e06_alice", "rep044_e03_alice")
SERVED = "gemini-3.8-flash"
PRIMARY = {"G": ("R4", "workflow gap: Detection(R4-om) - Detection(R1-om)"),
           "H": ("R2", "history effect: Detection(R2-om) - Detection(R1-om)"),
           "C": ("R1+CHK", "check instruction: Detection(R1-om+CHK) - Detection(R1-om)")}
OM_CELLS = [(v, "omission") for v in a16.OM_VARIANTS]
COR_CELLS = [(v, "correct") for v in a16.COR_VARIANTS]
ALL_CELLS = OM_CELLS + COR_CELLS + [a16.COM_CELL]
FR_ROW5_MAX = 0.05
ROW2_R1_MIN = 0.90


def _counterpart(v: str) -> str:
    return "R0p" if v == "R1" else v


def _om(calls, v, missing="exclude"):
    return cell(calls, v, "omission", missing=missing)


def _cor(calls, v, missing="exclude"):
    return cell(calls, _counterpart(v), "correct", missing=missing)


def _equiv(r: dict):
    lo, hi = r.get("ci_low"), r.get("ci_high")
    return None if lo is None else bool(lo >= -EQUIV_MARGIN and hi <= EQUIV_MARGIN)


def contrast_series(calls, x, missing="exclude") -> pd.Series:
    return paired(_om(calls, x, missing), _om(calls, "R1", missing))


def D_series(calls, x, missing="exclude") -> pd.Series:
    return paired(paired(_om(calls, x, missing), _cor(calls, x, missing)),
                  paired(_om(calls, "R1", missing), _cor(calls, "R1", missing)))


def primary(calls: pd.DataFrame, meta, missing="exclude") -> dict:
    out, pv = {}, {}
    for k, (x, label) in PRIMARY.items():
        res = test_contrast(contrast_series(calls, x, missing), meta)
        res.update(contrast=f"Detection({x}) - Detection(R1), omission versions", label=label)
        res["ci_inside_equivalence_margin"] = _equiv(res)
        out[k] = res
        if res["p"] is not None:
            pv[k] = res["p"]
    adj = holm(pv) if pv else {}
    for k, (x, _) in PRIMARY.items():
        out[k]["p_holm"] = adj.get(k)
        out[k]["significant"] = adj.get(k) is not None and adj[k] < ALPHA
        dd = D_series(calls, x, missing)
        if out[k]["significant"]:
            r = test_contrast(dd, meta)
            r["tested"] = True
            r["significant"] = r["p"] is not None and r["p"] < ALPHA
        else:
            r = dict(_ci(dd, meta), tested=False, note=f"{k} not significant: D not tested (gatekeeping, plan 8.6)")
        r["definition"] = f"D_i = [y({x},om) - y({x},correct)] - [y(R1,om) - y(R0',correct)]"
        out[f"D_{k}"] = r
    out["equivalence_margin"] = EQUIV_MARGIN
    return out


def interpretation(calls: pd.DataFrame, meta, prim: dict) -> dict:
    """The six A16 rows, applied literally (primary item set, missing excluded)."""
    r1 = _om(calls, "R1")
    det_r1 = float(r1.mean()) if len(r1) else None
    fr_chk = paired(_cor(calls, "R1+CHK"), _cor(calls, "R1"))
    fr_chk_est = float(fr_chk.mean()) if len(fr_chk) else None
    G, H, C = prim["G"], prim["H"], prim["C"]
    g_pos = G["significant"] and G["estimate"] > 0
    h_pos = H["significant"] and H["estimate"] > 0
    c_sig = C["significant"]
    rows = {
        "row1_G_significant_positive": bool(g_pos),
        "row2_G_not_significant_and_R1om_ge_0p90": bool(not G["significant"] and det_r1 is not None
                                                       and det_r1 >= ROW2_R1_MIN),
        "row3_G_not_significant_and_R1om_lt_0p90": bool(not G["significant"] and det_r1 is not None
                                                       and det_r1 < ROW2_R1_MIN),
        "row4_H_significant_positive": bool(h_pos),
        "row5a_C_significant_FR_rise_le_0p05": bool(c_sig and fr_chk_est is not None and fr_chk_est <= FR_ROW5_MAX),
        "row5b_C_significant_FR_rise_gt_0p05": bool(c_sig and fr_chk_est is not None and fr_chk_est > FR_ROW5_MAX),
        "row5c_C_not_significant": bool(not c_sig),
    }
    notes = []
    if G["significant"] and G["estimate"] <= 0:
        notes.append("G significant but negative: not covered by rows 1-3 (row 6); closest row 1, which needs a "
                     "positive G")
    if H["significant"] and H["estimate"] <= 0:
        notes.append("H significant but negative: row 4 does not apply (row 6)")
    if c_sig and C["estimate"] <= 0:
        notes.append("C significant but negative: row 5 assumes a positive transfer (row 6)")
    return dict(rows=rows, detection_R1_om=det_r1, FR_R1CHK_minus_R0p_point=fr_chk_est,
                G_ci_inside_equivalence_margin=G["ci_inside_equivalence_margin"], row6_notes=notes,
                definitions={"significant": "Holm-adjusted p < 0.05", "row2/3 threshold": ROW2_R1_MIN,
                             "row5 FR threshold (point estimate)": FR_ROW5_MAX})


def verifier_comparison(x16: pd.DataFrame, fl: pd.DataFrame, meta) -> dict:
    """3.8 Flash minus Flash-Lite, paired by item (descriptive, cluster bootstrap CIs, no test)."""
    out = {"cells": {}, "contrasts": {}}
    for v, ver in ALL_CELLS:
        a, b = cell(x16, v, ver), cell(fl, v, ver)
        out["cells"][f"{v}|{ver}"] = dict(flash_38=_ci(a, meta), flash_lite=_ci(b, meta),
                                          difference=_ci(paired(a, b), meta))
    for k, (x, _) in PRIMARY.items():
        a, b = contrast_series(x16, x), contrast_series(fl, x)
        out["contrasts"][k] = dict(flash_38=_ci(a, meta), flash_lite=_ci(b, meta), difference=_ci(paired(a, b), meta))
    return out


def com_markers() -> dict:
    from src.runner.item_lists import load_bait
    return {i: load_bait(i)["right_reason_markers"] for i in a16.shared_items()}


def secondary(calls: pd.DataFrame, meta, info: pd.DataFrame) -> dict:
    r0p = _cor(calls, "R1")
    out = {"per_cell": {}}
    cm = com_markers()
    for v, ver in ALL_CELLS:
        s = cell(calls, v, ver)
        res = {"rate_reject": _ci(s, meta)}
        sub = calls[(calls.variant == v) & (calls.version == ver)]
        if ver == "correct":
            res["false_rejection"] = res["rate_reject"]
            if v != "R0p":
                d = paired(s, r0p)
                res["false_rejection_minus_R0p"] = dict(_ci(d, meta))
                res["false_rejection_minus_R0p"]["ci_inside_equivalence_margin"] = _equiv(
                    res["false_rejection_minus_R0p"])
        else:
            mk = cm if ver == "bait" else info["markers"].to_dict()
            rej, acc = sub[sub.y == 1], sub[sub.y == 0]
            res["detection"] = res["rate_reject"]
            res["right_reason_deterministic"] = {
                "rejects": len(rej), "right_reason": int(sum(right_reason(t, mk[i]) for t, i in zip(rej.reasoning, rej.item_id)))}
            res["named_accept"] = {
                "accepts": len(acc), "named_accept": int(sum(right_reason(t, mk[i]) for t, i in zip(acc.reasoning, acc.item_id)))}
        piv = sub.dropna(subset=["y"]).pivot_table(index="item_id", columns="draw", values="y")
        if piv.shape[1] >= 2:
            both = piv.dropna()
            res["draw_agreement"] = {"items_with_two_draws": len(both),
                                     "agree_share": float((both.iloc[:, 0] == both.iloc[:, 1]).mean()) if len(both) else None}
        res["missing"] = int(sub.y.isna().sum())
        res["calls"] = len(sub)
        out["per_cell"][f"{v}|{ver}"] = res
    return out


def block(x16: pd.DataFrame, fl: pd.DataFrame, meta, info, items: list[str]) -> dict:
    x16 = x16[x16.item_id.isin(items)]
    fl = fl[fl.item_id.isin(items)]
    res = {"n_items": int(x16.item_id.nunique()), "n_clusters": int(meta.loc[sorted(set(x16.item_id)), "cluster"].nunique())
           if len(x16) else 0,
           "primary": primary(x16, meta)}
    for miss in ("accept", "reject"):
        res[f"primary_missing_as_{miss}"] = primary(x16, meta, missing=miss)
    res["interpretation"] = interpretation(x16, meta, res["primary"])
    res["verifier_comparison"] = verifier_comparison(x16, fl, meta)
    res["secondary"] = secondary(x16, meta, info)
    return res


def flash_lite_frame(main_calls: pd.DataFrame) -> pd.DataFrame:
    """The existing Flash-Lite cells on the same items and contexts, labeled as the A16 cells."""
    items = sorted(o["item_id"] for o in a16.omission_items())
    base = baseline_cells(main_calls.assign(check="MAIN"), load_stage("a06"))
    base = base[base.variant.isin(["R1", "R4", "R0p"])]
    a13 = load_stage("a13")
    a14 = load_stage("a14")
    chk = a14[(a14.variant == "CHK") & a14.version.isin(["omission", "correct"])].assign(variant="R1+CHK")
    com = main_calls[main_calls.item_id.isin(a16.shared_items()) & (main_calls.variant == "R1")
                     & (main_calls.version == "bait")]
    fl = pd.concat([base, a13[a13.variant == "R2"], chk, com], ignore_index=True)
    return fl[fl.item_id.isin(items)]


def served_models() -> dict:
    """Served-model evidence over all live a16 call lines (response_models of every usage record)."""
    from collections import Counter
    c, acc, n = Counter(), Counter(), 0
    for r in iter_call_lines(RAW):
        if r.get("stage") != STAGE or r.get("mode") != "live":
            continue
        n += 1
        for m in r.get("response_models") or []:
            c[m] += 1
        for u in r.get("usage") or []:
            if u.get("response_model") and not u.get("error_category"):
                acc[normalize_model(u["response_model"])] += 1
    return {"call_lines": n, "response_models_entries": dict(c), "accepted_responses_by_model": dict(acc),
            "only_expected_model": set(acc) <= {SERVED} and set(map(normalize_model, c)) <= {SERVED},
            "note": "served weights cannot be verified beyond Google's documentation (D39)"}


def load_exclusions() -> dict | None:
    return json.loads(EXCLUSIONS.read_text()) if EXCLUSIONS.exists() else None


def analyze(main_calls: pd.DataFrame, main_meta: pd.DataFrame) -> dict:
    exc = load_exclusions()
    if exc is None:
        return {"status": "awaiting exclusion freeze",
                "note": "data/derived/a16/primary_exclusions.json not written; no A16 outcome is read before it exists"}
    x16 = load_stage(STAGE)
    if x16.empty:
        return {"status": "not run", "exclusions": exc}
    meta, info = cluster_meta(), items_info()
    fl = flash_lite_frame(main_calls)
    all_items = sorted(o["item_id"] for o in a16.omission_items())
    prim_items = [i for i in all_items if i not in set(exc["excluded"])]
    out = {"label": "ADDENDUM A16 (D39; exploratory transfer study): " + a16.LABEL_38_FLASH +
                    "; primary family of three with Holm; fixed before any A16 call",
           "exclusions": exc, "calls": len(x16),
           "calls_by_cell": {f"{v}|{ver}": int(n) for (v, ver), n in x16.groupby(["variant", "version"]).size().items()},
           "missing": int(x16.y.isna().sum()), "flash_lite_missing": int(fl.y.isna().sum()),
           "served_models": served_models(),
           "primary_item_set": block(x16, fl, meta, info, prim_items),
           "all_50_sensitivity": block(x16, fl, meta, info, all_items),
           "without_all_d40_flagged_sensitivity": block(
               x16, fl, meta, info, [i for i in all_items if i not in set(exc["d40"]["flagged_items"])])}
    out["spend_usd_a16"] = float(sum(r.get("cost_usd") or 0 for r in iter_call_lines(RAW)
                                     if r.get("stage") == STAGE and r.get("mode") == "live"))
    return out


# ------------------------------------------------------------------ exclusion freeze (reads no A16 outcome)

def _git(*args) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def d40_flagged(path: Path) -> list[str]:
    d = pd.read_csv(path)
    return sorted(d.loc[d.flagged.astype(str).str.lower().isin(["true", "1"]), "item_id"])


def freeze_exclusions(d40_file: Path = D40_SCAN) -> dict:
    """Write EXCLUSIONS: the primary exclusions (Nick, D39: rep041_e06, rep044_e03) and the 4 D40-flagged items (column
    `flagged` of the committed, unmodified D40 scan; for the sensitivity), with the scan's commit and SHA-256. Fails
    closed if the scan is not committed or does not flag both primary exclusions. Reads no A16 outcome."""
    import hashlib
    if EXCLUSIONS.exists():
        raise SystemExit(f"{EXCLUSIONS} exists; exclusions are frozen once")
    rel = str(Path(d40_file).resolve().relative_to(ROOT))
    if not (ROOT / rel).exists() or not _git("ls-files", rel) or _git("status", "--porcelain", "--", rel):
        raise SystemExit(f"D40 scan {rel} is missing, not committed or locally modified")
    flagged = d40_flagged(ROOT / rel)
    all_items = {o["item_id"] for o in a16.omission_items()}
    if not set(flagged) <= all_items or not set(PRIMARY_EXCLUSIONS) <= set(flagged):
        raise SystemExit(f"D40 flags {flagged} do not contain the primary exclusions {PRIMARY_EXCLUSIONS}")
    rec = {"excluded": sorted(PRIMARY_EXCLUSIONS),
           "rule": "primary item set = 50 D25 items minus rep041_e06 (pre-specified, A16) and rep044_e03 (the second "
                   "genuine residue in D40; Nick's decision recorded in D39 before any A16 call); sensitivities: all "
                   "50 items, and without all D40-flagged items",
           "d40": {"file": rel, "commit": _git("log", "-1", "--format=%H %cI", "--", rel),
                   "sha256": hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), "flagged_items": flagged},
           "frozen_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "head": _git("rev-parse", "HEAD"),
           "a16_call_lines_at_freeze": sum(1 for r in iter_call_lines(RAW) if r.get("stage") == STAGE
                                           and r.get("mode") == "live")}
    EXCLUSIONS.parent.mkdir(parents=True, exist_ok=True)
    EXCLUSIONS.write_text(json.dumps(rec, indent=2) + "\n")
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="A16 analysis helpers")
    ap.add_argument("--freeze-exclusions", action="store_true")
    a = ap.parse_args(argv)
    if a.freeze_exclusions:
        print(json.dumps(freeze_exclusions(), indent=2))


if __name__ == "__main__":
    main()
