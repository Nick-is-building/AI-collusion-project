"""Study 2 sensitivities fixed by Nick before the C′ relaunch (A05b, D32; assignments/A05b_study2_relaunch.md).

In addition to the preregistered primary on all 50 pairs (src/hysteresis/analysis.py, unchanged):
  (1) the primary B − C′ test (same procedure: paired t-test + sequence bootstrap, episodes 6–8, both
      directions) on the 18 sequences whose C′ was not rerun (rep001–013, rep046–050);
  (2) C′-only drift check: mean strict_full episodes 6–8, rerun C′ (32 sequences, rep014–045) versus
      original C′ (18), difference rerun − original with a sequence bootstrap CI (sequences resampled
      with replacement within each group, 10,000 resamples, seed 2026, percentile 95%); descriptive;
  (3) the B→C′ launch lag per sequence: started_at of the counted C′ run minus started_at of the
      counted B run, from study2_meta.json (minutes). Operational, no outcome.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.hysteresis import analysis as A
from src.hysteresis.scheduler import scan

RERUN_SEQS = tuple(range(14, 46))                                      # C′ rerun under A05b (32)
NOT_RERUN_SEQS = tuple(list(range(1, 14)) + list(range(46, 51)))       # 18


def primary_not_rerun(rows: pd.DataFrame) -> dict:
    sub = rows[rows.seq.isin(NOT_RERUN_SEQS)]
    out = A.paired_contrast(A.seq_means(sub, "B"), A.seq_means(sub, "Cprime"),
                            "A05b (1): H6 primary procedure on the 18 sequences whose C' was not rerun",
                            "B", "Cprime")
    out["seqs"] = list(NOT_RERUN_SEQS)
    return out


def two_group_bootstrap(x, y, n_boot: int = A.N_BOOT, seed: int = A.SEED, level: float = 0.95) -> dict:
    """Percentile CI of mean(x) − mean(y), resampling sequences with replacement within each group."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    rng = np.random.default_rng(seed)
    bx = x[rng.integers(0, len(x), (n_boot, len(x)))].mean(axis=1)
    by = y[rng.integers(0, len(y), (n_boot, len(y)))].mean(axis=1)
    a = (1 - level) / 2
    lo, hi = np.percentile(bx - by, [100 * a, 100 * (1 - a)])
    return {"lo": float(lo), "hi": float(hi), "n_boot": n_boot, "seed": seed}


def cprime_drift_rerun_vs_original(rows: pd.DataFrame) -> dict:
    c = A.seq_means(rows, "Cprime")
    rerun, orig = c[c.index.isin(RERUN_SEQS)], c[c.index.isin(NOT_RERUN_SEQS)]
    out = {"label": "A05b (2): C' drift check, rerun C' (rep014-045) - original C' (rep001-013, rep046-050), "
                    "strict_full episodes 6-8; descriptive",
           "n_rerun": len(rerun), "n_original": len(orig),
           "mean_rerun": A._mean(rerun), "mean_original": A._mean(orig)}
    if len(rerun) >= 2 and len(orig) >= 2:
        out.update(diff_rerun_minus_original=float(rerun.mean() - orig.mean()),
                   ci95_bootstrap=two_group_bootstrap(rerun, orig))
    return out


def _counted_meta(group_dir: Path, seq: int, arm: str) -> dict | None:
    st = scan(group_dir, seq, arm)
    run = st.complete_run()
    if run is None:
        return None
    return next(m for p, _, m in st.runs if p == run)


def launch_lags(group_dir: Path, seqs) -> pd.DataFrame:
    rows = []
    for seq in seqs:
        b, c = _counted_meta(group_dir, seq, "B"), _counted_meta(group_dir, seq, "Cprime")
        lag = None
        if b and c:
            lag = (datetime.fromisoformat(c["started_at"]) - datetime.fromisoformat(b["started_at"])).total_seconds() / 60
        rows.append({"seq": seq, "rerun": seq in RERUN_SEQS, "B_started_at": b and b["started_at"],
                     "Cprime_started_at": c and c["started_at"], "lag_min_Cprime_minus_B": lag})
    return pd.DataFrame(rows)


def lag_summary(lags: pd.DataFrame) -> dict:
    out = {"label": "A05b (3): B->C' launch lag per sequence (C' started_at - B started_at, minutes, "
                    "counted runs, study2_meta.json)", "per_seq": lags.to_dict("records")}
    for name, g in (("rerun", lags[lags.rerun]), ("not_rerun", lags[~lags.rerun])):
        v = g.lag_min_Cprime_minus_B.dropna()
        out[name] = {"n": len(v), "median": float(v.median()) if len(v) else None,
                     "min": float(v.min()) if len(v) else None, "max": float(v.max()) if len(v) else None}
    return out


def sensitivities(rows: pd.DataFrame, group_dir: Path, seqs) -> dict:
    return A.to_jsonable({"primary_not_rerun_18": primary_not_rerun(rows),
                          "cprime_drift_rerun_vs_original": cprime_drift_rerun_vs_original(rows),
                          "launch_lag_B_to_Cprime": lag_summary(launch_lags(Path(group_dir), seqs))})
