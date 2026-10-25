"""A05b sensitivities (src/hysteresis/sensitivity_a05b.py), next to the preregistered analysis.

    PYTHONPATH=. .venv/bin/python -m scripts.study2.analyze_a05b --runs results/study2/main/runs.csv \
        --group-dir results/study2/main --out results/summaries/study2_a05b_sensitivities.json --confirm-run-complete

Same refusal rule as scripts/study2/analyze.py: no outcome number unless --confirm-run-complete and
every arm in the run list is complete. `--lags-only` prints the launch lags (operational, no outcome).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.hysteresis import analysis as A
from src.hysteresis import sensitivity_a05b as S


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--group-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--confirm-run-complete", action="store_true")
    ap.add_argument("--lags-only", action="store_true")
    a = ap.parse_args(argv)
    rl = A.load_run_list(a.runs)
    seqs = sorted(rl.seq.unique())
    if a.lags_only:
        print(json.dumps(A.to_jsonable(S.lag_summary(S.launch_lags(Path(a.group_dir), seqs))), indent=1))
        return 0
    if not a.confirm_run_complete:
        print("refusing: needs --confirm-run-complete", file=sys.stderr)
        return 2
    eps = [{"seq": r.seq, "arm": r.arm, **A._episode_summary(A.load_run(r.run_json))} for r in rl.itertuples()]
    comp = A.completeness(pd.DataFrame(eps, columns=["seq", "arm", "n_episodes", "contiguous"]), rl.seq)
    if not comp.complete.all():
        print(f"refusing: {int((~comp.complete).sum())} (seq, arm) incomplete or missing", file=sys.stderr)
        return 2
    rows = A.collect(rl)["verdict_rows"]
    res = S.sensitivities(rows, Path(a.group_dir), seqs)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
