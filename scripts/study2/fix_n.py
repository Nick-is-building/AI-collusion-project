"""D21: fix the number of Study 2 pairs from cost only, after P8 and before launch.

Rule (Nick, D21, verbatim in assignments/A05_study2_build_launch.md): use the measured cost per
sequence from P8 (including the cache share actually observed) plus a 15% reserve; take the
largest n of 50, 40, 30 that fits the remaining Study 2 cap. Sequences are rep001 onward in order.
If 30 does not fit, Study 2 is dropped. No outcome is read: inputs are the P8 usage journals
(cost and tokens), the P8 run metadata (completeness), the Study 2 stage cap and the project hard
cap from configs/caps.yaml, and the project ledger (results/raw).
"Remaining" is checked against both the Study 2 stage cap and the project hard cap; n must fit both.

    PYTHONPATH=. .venv/bin/python -m scripts.study2.fix_n --out results/summaries/study2_n.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.hysteresis.guard import STAGE, JournalLedger
from src.hysteresis.scheduler import EXPECTED, scan
from src.runner.costs import Ledger, load_yaml

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = (50, 40, 30)
RESERVE = 0.15


def decide(cost_per_sequence: float, study2_spent: float, stage_cap: float, project_spent: float,
           hard_cap: float) -> dict:
    per_seq = cost_per_sequence * (1 + RESERVE)
    remaining = min(stage_cap - study2_spent, hard_cap - project_spent - study2_spent)
    fits = [n for n in CANDIDATES if n * per_seq <= remaining]
    n = max(fits) if fits else None
    return {"cost_per_sequence_measured": round(cost_per_sequence, 4), "reserve": RESERVE,
            "cost_per_sequence_with_reserve": round(per_seq, 4),
            "remaining_study2_cap": round(stage_cap - study2_spent, 4),
            "remaining_hard_cap": round(hard_cap - project_spent - study2_spent, 4),
            "remaining_binding": round(remaining, 4),
            "projected_by_n": {c: round(c * per_seq, 2) for c in CANDIDATES},
            "n": n, "dropped": n is None,
            "sequences": [f"rep{i:03d}" for i in range(1, n + 1)] if n else []}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--p8-group", default="p8")
    ap.add_argument("--p8-seq", type=int, default=1)
    ap.add_argument("--out", default="results/summaries/study2_n.json")
    a = ap.parse_args(argv)
    root = Path(a.out_root)
    for arm in EXPECTED:
        st = scan(root / a.p8_group, a.p8_seq, arm)
        if not st.complete:
            raise SystemExit(f"P8 arm {arm} is not complete; n cannot be fixed from a partial sequence")
    led = JournalLedger(root).refresh()
    groups = led.by_group()
    if set(groups) - {a.p8_group}:
        raise SystemExit(f"Study 2 spend outside P8 exists ({groups}); n must be fixed before any main-run call")
    caps = load_yaml("caps.yaml")
    project = Ledger(ROOT / "results" / "raw", mode="live").total
    out = decide(groups.get(a.p8_group, 0.0), led.total, caps["stages"][STAGE], project, caps["hard_cap_usd"])
    out.update({"p8_group": a.p8_group, "p8_seq": a.p8_seq, "project_spent_other_stages": round(project, 4),
                "study2_spent": round(led.total, 4), "stage_cap": caps["stages"][STAGE],
                "hard_cap": caps["hard_cap_usd"], "rule": "D21 (assignment A05)"})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
