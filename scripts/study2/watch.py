"""Operational watcher: exit (and print why) as soon as something needs attention (plan 23.3).

Exit conditions: an error category or rate-limit error appears in the journals, more than one
response model, a STOP file, a failed arm attempt, the scheduler ended, or the watched sequence
has all five arms complete. Reads only what scripts/study2/monitor.py reads (no outcome).

    PYTHONPATH=. .venv/bin/python -m scripts.study2.watch --group main --seqs 1-50 --until-seq 1
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scripts.study2.launch import parse_seqs
from scripts.study2.monitor import summarize
from src.hysteresis.scheduler import EXPECTED, scan


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--until-seq", type=int, default=None)
    ap.add_argument("--poll", type=float, default=60)
    ap.add_argument("--max-minutes", type=float, default=600)
    a = ap.parse_args(argv)
    root, gdir = Path(a.out_root), Path(a.out_root) / a.group
    t0 = time.time()
    while True:
        s = summarize(gdir, parse_seqs(a.seqs))
        why = []
        if s["error_categories"]:
            why.append(f"errors {s['error_categories']}")
        if len(s["response_models"]) > 1:
            why.append(f"response models {s['response_models']}")
        if (root / "STOP").exists():
            why.append("STOP file")
        if s.get("arms_failed_attempts"):
            why.append(f"failed attempts {s['arms_failed_attempts']}")
        ev = gdir / "scheduler.jsonl"
        if ev.exists() and '"scheduler_end"' in ev.read_text():
            why.append("scheduler ended")
        if a.until_seq and all(scan(gdir, a.until_seq, arm).complete for arm in EXPECTED):
            why.append(f"sequence {a.until_seq} complete")
        if time.time() - t0 > a.max_minutes * 60:
            why.append("max minutes")
        if why:
            print(json.dumps({"why": why, **{k: s[k] for k in ("calls", "cost_usd", "cached_share", "rate_limit_errors",
                                                              "arms_complete", "projected_cost_usd")}}))
            return
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
