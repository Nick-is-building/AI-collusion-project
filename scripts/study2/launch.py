"""Launch or continue Study 2 runs (P8 or the main run) through the resumable scheduler.

    # dry run, mock model, no API calls:
    PYTHONPATH=. .venv/bin/python -m scripts.study2.launch --group dry --seqs 1-2 --workers 8 --backend mock \
        --out-root scratch/s2dry
    # live (only with Nick's authorization of the stage; clean committed tree; caps in configs/caps.yaml):
    set -a; . ./.env; set +a
    PYTHONPATH=. nohup .venv/bin/python -m scripts.study2.launch --group p8 --seqs 1 --workers 5 \
        --backend live --approved-stage study2 > logs/study2_p8.log 2>&1 &

Re-running the same command continues: finished arms are skipped, partial arms resume from their
last episode boundary (src/hysteresis/scheduler.py). Workers can be changed while running by
writing a number to <out-root>/<group>/WORKERS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.hysteresis.scheduler import EXPECTED, Scheduler


def parse_seqs(text: str) -> list[int]:
    out = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    if not out or min(out) < 1 or max(out) > 50 or len(set(out)) != len(out):
        raise SystemExit(f"bad --seqs {text!r} (1..50, no repeats)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--seqs", required=True, help="e.g. 1 or 1-50")
    ap.add_argument("--workers", type=int, required=True)
    ap.add_argument("--backend", required=True, choices=("mock", "live"))
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--reserve-slots", type=int, default=None,
                    help="cost-guard reserve slots per process (default: the worker limit at launch)")
    ap.add_argument("--plan", action="store_true", help="print what would be launched now, launch nothing")
    ap.add_argument("--reset-attempts", default="", metavar="REASON",
                    help="log an attempts_reset event (launch counts restart from here), e.g. after a fixed "
                         "launcher bug; the reason is recorded")
    a = ap.parse_args(argv)
    if a.backend == "live" and a.approved_stage != "study2":
        raise SystemExit("live needs --approved-stage study2")
    s = Scheduler(out_root=Path(a.out_root), group=a.group, seqs=parse_seqs(a.seqs), workers=a.workers,
                  backend=a.backend, approved_stage=a.approved_stage, reserve_slots=a.reserve_slots)
    if a.reset_attempts:
        s.log(event="attempts_reset", reason=a.reset_attempts)
    if a.plan:
        states = s.state()
        for (seq, arm), st in sorted(states.items()):
            cmd = s.command(st, states)
            print(f"rep{seq:03d} {arm:7s} runs={st.attempts} complete={st.complete} "
                  f"next={'-' if st.complete else ('waiting' if cmd is None else 'ready')}")
        print(f"arms: {len(states)} ({len(s.seqs)} sequences x {len(EXPECTED)})")
        return
    result = s.run()
    print(json.dumps({k: v for k, v in result.items()}, default=str))


if __name__ == "__main__":
    main()
