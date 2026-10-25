"""Worker limit for the A05b resume (Nick, 25 October 2026, about 01:30 UTC): 3 workers while the A10
run is active, then up to 6 once A10 has finished; never ramp up while any 429 occurs.

Writes <out-root>/<group>/WORKERS (read by the scheduler while running):
  - LOW while any `scripts.a10` process is alive (lowering is applied at once);
  - HIGH only when no `scripts.a10` process has been seen for QUIET_S seconds AND no quota 429 was
    recorded in the group's usage journals in the last QUIET_S seconds.
Each change is appended to scheduler.jsonl as a `workers_set` event. Exits when the scheduler ends
(a scheduler_end event after this process started). Reads no outcome.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.study2.stop_watch import Tail, is_429
from src.hysteresis.guard import JOURNAL

QUIET_S = 600


def a10_alive() -> bool:
    """A Python process whose argv has a module argument starting with `scripts.a10` (shells whose
    command text merely mentions it, e.g. another session's wait loops, do not count)."""
    for d in Path("/proc").iterdir():
        if not d.name.isdigit() or int(d.name) == os.getpid():
            continue
        try:
            argv = (d / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        if argv and "python" in Path(argv[0]).name and any(x.startswith("scripts.a10") for x in argv[1:]):
            return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--low", type=int, default=3)
    ap.add_argument("--high", type=int, default=6)
    ap.add_argument("--poll", type=float, default=30)
    a = ap.parse_args(argv)
    gdir = Path(a.out_root) / a.group
    started = datetime.now(timezone.utc)
    journals = Tail()
    journals.prime(sorted(gdir.rglob(JOURNAL)))
    last_a10 = last_429 = started            # conservative: both count as just seen at start
    current = None

    def set_workers(n, why):
        nonlocal current
        if n == current:
            return
        (gdir / "WORKERS").write_text(f"{n}\n")
        with open(gdir / "scheduler.jsonl", "a") as fh:
            fh.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "event": "workers_set",
                                 "workers": n, "why": why}) + "\n")
        current = n
        print(f"{datetime.now(timezone.utc).isoformat()} workers={n} ({why})", flush=True)

    while True:
        now = datetime.now(timezone.utc)
        for _, line in journals.lines(sorted(gdir.rglob(JOURNAL))):
            try:
                rec = json.loads(line)
                if is_429(rec) and datetime.fromisoformat(rec["recorded_at"]) >= started:
                    last_429 = now
            except (ValueError, KeyError):
                continue
        if a10_alive():
            last_a10 = now
            set_workers(a.low, "A10 process alive")
        elif now - last_a10 >= timedelta(seconds=QUIET_S) and now - last_429 >= timedelta(seconds=QUIET_S):
            set_workers(a.high, f"no A10 process and no quota 429 for {QUIET_S} s")
        elif current is None:
            set_workers(a.low, "start")
        ev = gdir / "scheduler.jsonl"
        for l in reversed(ev.read_text().splitlines()):
            r = json.loads(l)
            if datetime.fromisoformat(r["at"]) < started:
                break
            if r.get("event") == "scheduler_end":
                print("scheduler ended", flush=True)
                return
        time.sleep(a.poll)


if __name__ == "__main__":
    main()
