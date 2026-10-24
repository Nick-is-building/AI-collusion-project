"""Study 2 analysis CLI (src/hysteresis/analysis.py).

    .venv/bin/python -m scripts.study2.analyze --runs runs.csv --out results/summaries/study2_analysis.json \
        --confirm-run-complete
    .venv/bin/python -m scripts.study2.analyze --runs runs.csv --status-line-only

Outcome statistics are computed only with --confirm-run-complete AND when every seq in the run list
has all five arms with complete episodes (prefix 5, others 10): plan 9.2 allows no interim look at
the outcome. --status-line-only runs the operational status-line check (plan 23.3) and prints no
strict_full or verdict numbers; it is allowed before the run is complete.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.hysteresis import analysis as A  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="CSV with columns seq,arm,run_json")
    ap.add_argument("--out", default=str(ROOT / "results" / "summaries" / "study2_analysis.json"))
    ap.add_argument("--confirm-run-complete", action="store_true")
    ap.add_argument("--status-line-only", action="store_true")
    a = ap.parse_args(argv)
    rl = A.load_run_list(a.runs)

    if a.status_line_only:
        c = A.collect(rl, status_only=True)
        s = A.status_summary(c["status"])
        print(f"status-line check: {'PASS' if s['pass'] else 'FAIL'}; {s['n_rows']} rows, "
              f"{s['n_failures']} failures, {s['n_rows_with_mentions_beyond_opening']} rows with "
              f"mentions beyond the opening")
        for f in s["failures"][:50]:
            print(f"  seq={f['seq']} arm={f['arm']} ep={f['episode_index']} agent={f['agent']}: {f['reason']}")
        return 0 if s["pass"] else 1

    if not a.confirm_run_complete:
        print("refusing: outcome statistics need --confirm-run-complete (plan 9.2: no interim analysis)",
              file=sys.stderr)
        return 2
    # Completeness from the run files themselves, before any outcome number is computed.
    eps = [{"seq": r.seq, "arm": r.arm, **A._episode_summary(A.load_run(r.run_json))} for r in rl.itertuples()]
    comp = A.completeness(pd.DataFrame(eps, columns=["seq", "arm", "n_episodes", "contiguous"]), rl.seq)
    if not comp.complete.all():
        bad = comp[~comp.complete]
        print(f"refusing: {len(bad)} (seq, arm) incomplete or missing:", file=sys.stderr)
        for r in bad.itertuples():
            print(f"  seq={r.seq} arm={r.arm} episodes={r.n_episodes}/{r.expected}", file=sys.stderr)
        return 2
    res = A.analyze_all(rl)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    p = res["primary"]
    print(f"wrote {out}; status line {'PASS' if res['status_line']['pass'] else 'FAIL'}; "
          f"primary n={p['n']} mean_d={p.get('mean_d')} p={p.get('p_two_sided')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
