"""D40 sensitivity analysis (0 USD): every analysis that uses the D25 omission items, rerun with the same code and
methods without the items flagged by the residue scan (data/derived/residue_scan_d25.csv, column `flagged`).

Mechanism: the call-line reader `src.runner.costs.iter_call_lines` (and every module-level reference to it) is
wrapped so that it drops the call lines of the flagged item IDs; each addendum's own `analyze(main_calls, meta)`
then runs unchanged. Sections: A06 D25 (Delta_om, D_om), A10 (T1-T3, D), A13 (five-contrast ladder, D, equivalence),
A14 Task 1 (L1, L2, D, interpretation rows), A15 (its primary family). Output:
results/summaries/sensitivity_residue.json with both runs and a comparison table (`table`).

  PYTHONPATH=. .venv/bin/python -m scripts.d40.sensitivity
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "data" / "derived" / "residue_scan_d25.csv"
OUT = ROOT / "results" / "summaries" / "sensitivity_residue.json"
MODULES = ("a06_addendum", "a10_addendum", "a13_addendum", "a14_addendum", "a15_addendum")


def flagged() -> list[str]:
    t = pd.read_csv(SCAN)
    return sorted(t.item_id[t.flagged.astype(bool)])


def run(exclude: set[str]) -> dict:
    import src.runner.costs as costs
    orig = costs.__dict__.setdefault("_d40_orig_iter", costs.iter_call_lines)

    def filtered(results_dir):
        for r in orig(results_dir):
            if r.get("item_id") not in exclude:
                yield r
    mods = [importlib.import_module(f"scripts.analysis.{m}") for m in MODULES]
    for mod in [costs] + mods + [m for m in list(sys.modules.values()) if m is not None]:
        if getattr(mod, "iter_call_lines", None) in (orig, costs.iter_call_lines):
            mod.iter_call_lines = filtered
    for m in mods:   # per-module caches of item tables are independent of the call lines; clear any lru caches
        for v in vars(m).values():
            if hasattr(v, "cache_clear"):
                v.cache_clear()
    from src.analysis.meta import main_meta
    from src.analysis.primary import load_calls
    calls = load_calls(ROOT / "results" / "raw", "main", "MAIN", "live")
    meta = main_meta()
    a06, a10, a13, a14, a15 = mods
    out = {"A06_D25": a06.d25(calls.assign(check="MAIN"), a06.load_stage("a06"), a06.cluster_meta()),
           "A10": a10.analyze(calls, meta), "A13": a13.analyze(calls, meta),
           "A14_LOOK": a14.analyze(calls, meta).get("LOOK"), "A15": a15.analyze(calls, meta)}
    for mod in [costs] + mods + list(sys.modules.values()):
        if getattr(mod, "iter_call_lines", None) is filtered:
            mod.iter_call_lines = orig
    return out


TESTS = {   # (section, path to a test dict) for every pre-specified test on the D25 omission items
    "A06 Delta_om (R4-om - R1-om)": ("A06_D25", ["Delta_om_R4_minus_R1"]),
    "A06 D_om": ("A06_D25", ["D_om"]),
    **{f"A10 {k}": ("A10", ["primary", k]) for k in ("T1", "T2", "T3", "D_T1", "D_T2")},
    **{f"A13 {k}": ("A13", ["primary", k]) for k in ("R2_minus_R1", "R3_minus_R1", "R4_minus_R2", "R5_minus_R4",
                                                    "R4n_minus_R4", "D_R2_minus_R1", "D_R3_minus_R1", "D_R4_minus_R2",
                                                    "D_R5_minus_R4", "D_R4n_minus_R4")},
    **{f"A14 {k}": ("A14_LOOK", ["primary", k]) for k in ("L1", "L2", "D_L1", "D_L2")},
    **{f"A15 {k}": ("A15", ["primary", k]) for k in ("H_out", "H_work", "D_H_out", "D_H_work")},
}


def _get(d, path):
    for p in path:
        d = (d or {}).get(p)
    return d or {}


def _sig(t: dict):
    """Significance as the section defines it: Holm-adjusted where a p_holm exists, else p < 0.05 if tested."""
    if "significant" in t and t["significant"] is not None:
        return bool(t["significant"])
    if t.get("tested") is False:
        return "not tested"
    return None if t.get("p") is None else bool(t["p"] < 0.05)


def flags(r: dict) -> dict:
    f = {}
    for k, v in (_get(r, ["A14_LOOK", "interpretation_rows"]) or {}).items():
        if isinstance(v, bool):
            f[f"A14 row {k}"] = v
    for k, v in (_get(r, ["A13", "equivalence"]) or {}).items():
        f[f"A13 equivalence {k} explanation_rejected"] = v.get("explanation_rejected")
    for k in ("H_out", "H_work"):
        f[f"A15 {k} ci_inside_equivalence_margin"] = _get(r, ["A15", "primary", k]).get("ci_inside_equivalence_margin")
    return f


def table(full: dict, excl: dict) -> list[dict]:
    rows = []
    for name, (sec, path) in TESTS.items():
        a, b = _get(full[sec], path), _get(excl[sec], path)
        sa, sb = _sig(a), _sig(b)
        rows.append(dict(test=name, estimate=a.get("estimate"), ci=[a.get("ci_low"), a.get("ci_high")],
                         p=a.get("p"), p_holm=a.get("p_holm"), significant=sa, n_items=a.get("n_items"),
                         estimate_without=b.get("estimate"), ci_without=[b.get("ci_low"), b.get("ci_high")],
                         p_without=b.get("p"), p_holm_without=b.get("p_holm"), significant_without=sb,
                         n_items_without=b.get("n_items"), significance_changes=sa != sb))
    fa, fb = flags(full), flags(excl)
    for k in fa:
        rows.append(dict(test=k, estimate=fa[k], estimate_without=fb.get(k), significance_changes=fa[k] != fb.get(k)))
    return rows


def main():
    ex = flagged()
    full, excl = run(set()), run(set(ex))
    rows = table(full, excl)
    res = {"label": "D40 sensitivity (0 USD): analyses on the D25 omission items rerun without the items flagged by "
                    "the residue scan; same code and methods (cluster sign-flip 10,000 / bootstrap 10,000, seed 2026)",
           "excluded_items": ex, "scan_sha256": (SCAN.with_suffix(".sha256")).read_text().split()[0],
           "table": rows, "any_change": [r["test"] for r in rows if r["significance_changes"]],
           "full": full, "without_flagged": excl}
    from src.analysis.primary import to_json
    OUT.write_text(to_json(res))
    for r in rows:
        print(f"{r['test']:<60} {r['estimate']!s:>8.8} -> {r['estimate_without']!s:>8.8}  "
              f"sig {r.get('significant')} -> {r.get('significant_without')}  {'CHANGE' if r['significance_changes'] else ''}")
    print("excluded", ex, "changes:", res["any_change"])


if __name__ == "__main__":
    main()
