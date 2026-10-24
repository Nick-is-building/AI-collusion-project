"""Write the analysis run list (seq, arm, run_json) from the complete runs of one Study 2 group.

    PYTHONPATH=. .venv/bin/python -m scripts.study2.run_list --group main --seqs 1-50 --out results/study2/main/runs.csv
Incomplete arms are listed on stderr and left out (src/hysteresis/analysis.py refuses incomplete lists).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from scripts.study2.launch import parse_seqs
from src.hysteresis.scheduler import EXPECTED, scan


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    group_dir = Path(a.out_root).resolve() / a.group
    rows, missing = [], []
    for seq in parse_seqs(a.seqs):
        for arm in EXPECTED:
            st = scan(group_dir, seq, arm)
            (rows.append((seq, arm, str(st.complete_run()))) if st.complete else missing.append(f"rep{seq:03d}/{arm}"))
    with open(a.out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["seq", "arm", "run_json"])
        w.writerows(rows)
    print(f"{len(rows)} complete arms written to {a.out}; incomplete: {missing or 'none'}", file=sys.stderr)


if __name__ == "__main__":
    main()
