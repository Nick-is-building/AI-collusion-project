"""Fail-closed stop watcher for a Study 2 relaunch (A05b, Nick, 25 October 2026).

Writes the STOP file (<out-root>/STOP; src/hysteresis/guard.py then stops every run at its next call,
and the scheduler launches nothing) if
  1. any log line contains "spending cap" (case-insensitive): new content of the per-run logs
     (logs/study2/<group>/*.log), of the launcher log (--launcher-log), and the error_message of usage
     journal records under the group recorded after the watcher started; or
  2. more than MAX_429 quota 429s occur within WINDOW_S seconds: usage-journal records under the group
     with an error, recorded after the watcher started, whose error_message contains "429" or whose
     error_category is a rate-limit category, counted by their recorded_at time.
Single transient quota 429s are left to upstream's retry. Only content written after the watcher
started counts: log files that already exist are read from their current end, so the pre-relaunch
spend-cap lines of 24 October cannot trigger it.

While running it keeps <out-root>/<group>/stop_watch.json (rules, pid, start, heartbeat, state). The
scheduler with --require-stop-watch launches nothing while this process is not alive, and every run
records the file's content in its study2_meta.json (`stop_watch`). Reads no message, verdict or outcome.

    PYTHONPATH=. nohup .venv/bin/python -m scripts.study2.stop_watch --group main \
        --launcher-log logs/study2_main_relaunch.log > logs/study2_stop_watch.log 2>&1 &
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.hysteresis.guard import JOURNAL

ROOT = Path(__file__).resolve().parents[2]
SPEND_CAP_TEXT = "spending cap"
MAX_429 = 10
WINDOW_S = 300
RATE_LIMIT_CATEGORIES = {"transient_rate_limit", "hard_quota"}
RULES = {"spending_cap_text": SPEND_CAP_TEXT, "max_quota_429": MAX_429, "window_s": WINDOW_S,
         "rule": f"STOP if any log line contains {SPEND_CAP_TEXT!r} or more than {MAX_429} quota 429s "
                 f"within {WINDOW_S} s; single transient 429s keep upstream's retry",
         "source": "assignments/A05b_study2_relaunch.md"}
STATE_FILE = "stop_watch.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_429(rec: dict) -> bool:
    if not (rec.get("error_category") or rec.get("error_type") or rec.get("error_message")):
        return False
    return "429" in str(rec.get("error_message") or "") or rec.get("error_category") in RATE_LIMIT_CATEGORIES


def watcher_alive(state_path: Path) -> bool:
    """True if the state file names a live stop_watch process."""
    try:
        st = json.loads(Path(state_path).read_text())
        return b"scripts.study2.stop_watch" in Path(f"/proc/{int(st['pid'])}/cmdline").read_bytes()
    except (OSError, ValueError, KeyError, TypeError):
        return False


class Tail:
    """New complete lines of a set of files; existing files start at their end (pre-start content is skipped)."""

    def __init__(self):
        self.offsets: dict[Path, int] = {}

    def prime(self, files):
        for f in files:
            self.offsets[f] = f.stat().st_size

    def lines(self, files):
        for f in files:
            off = self.offsets.setdefault(f, 0)
            try:
                with open(f, "rb") as fh:
                    fh.seek(off)
                    chunk = fh.read()
            except OSError:
                continue
            end = chunk.rfind(b"\n") + 1
            self.offsets[f] = off + end
            for line in chunk[:end].splitlines():
                yield f, line.decode("utf-8", "replace")


class StopWatch:
    def __init__(self, *, out_root: Path, group: str, log_dir: Path, launcher_log: Path | None = None,
                 max_429: int = MAX_429, window_s: float = WINDOW_S):
        self.out_root, self.group = Path(out_root), group
        self.gdir = self.out_root / group
        self.gdir.mkdir(parents=True, exist_ok=True)
        self.log_dir = Path(log_dir)
        self.launcher_log = Path(launcher_log) if launcher_log else None
        self.max_429, self.window_s = max_429, window_s
        self.started = utc_now()
        self.logs, self.journals = Tail(), Tail()
        self.logs.prime(self.log_files())
        self.journals.prime(self.journal_files())   # earlier records are filtered by recorded_at as well
        self.recent_429: deque = deque()
        self.n_429 = 0
        self.state_path = self.gdir / STATE_FILE
        self.write_state("watching")

    def log_files(self):
        fs = sorted(self.log_dir.glob("*.log")) if self.log_dir.exists() else []
        if self.launcher_log and self.launcher_log.exists():
            fs.append(self.launcher_log)
        return fs

    def journal_files(self):
        return sorted(self.gdir.rglob(JOURNAL))

    def write_state(self, state: str, reason: str = ""):
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"rules": RULES, "max_429": self.max_429, "window_s": self.window_s,
                                   "pid": os.getpid(), "group": self.group, "started_at": self.started.isoformat(),
                                   "heartbeat_at": utc_now().isoformat(), "state": state, "reason": reason,
                                   "quota_429_seen": self.n_429 if hasattr(self, "n_429") else 0}, indent=1))
        tmp.replace(self.state_path)

    def stop(self, reason: str):
        stop = self.out_root / "STOP"
        if not stop.exists():
            stop.write_text(f"{utc_now().isoformat()} stop_watch: {reason}\n")
        with open(self.gdir / "scheduler.jsonl", "a") as fh:      # append-only operator event
            fh.write(json.dumps({"at": utc_now().isoformat(), "event": "stop_watch_stop", "reason": reason}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.write_state("stopped", reason)

    def check(self) -> str | None:
        """One pass; returns the stop reason or None."""
        for f, line in self.logs.lines(self.log_files()):
            if SPEND_CAP_TEXT in line.lower():
                return f"log line contains {SPEND_CAP_TEXT!r}: {f.name}: {line.strip()[:200]}"
        now = utc_now()
        for f, line in self.journals.lines(self.journal_files()):
            try:
                rec = json.loads(line)
                at = datetime.fromisoformat(rec["recorded_at"])
            except (ValueError, KeyError, TypeError):
                continue
            if at < self.started:
                continue
            if SPEND_CAP_TEXT in str(rec.get("error_message") or "").lower():
                return f"journal error contains {SPEND_CAP_TEXT!r}: {f.parent.name}"
            if is_429(rec):
                self.recent_429.append(at)
                self.n_429 += 1
        while self.recent_429 and self.recent_429[0] < now - timedelta(seconds=self.window_s):
            self.recent_429.popleft()
        if len(self.recent_429) > self.max_429:
            return f"{len(self.recent_429)} quota 429s within {self.window_s:.0f} s (limit {self.max_429})"
        return None

    def scheduler_ended(self) -> bool:
        ev = self.gdir / "scheduler.jsonl"
        if not ev.exists():
            return False
        for line in reversed(ev.read_text().splitlines()):
            rec = json.loads(line)
            if datetime.fromisoformat(rec["at"]) < self.started:
                return False
            if rec.get("event") == "scheduler_end":
                return True
        return False

    def run(self, poll_s: float = 5.0) -> str:
        while True:
            reason = self.check()
            if reason:
                self.stop(reason)
                return f"STOP: {reason}"
            if self.scheduler_ended():
                self.write_state("ended", "scheduler ended")
                return "scheduler ended"
            self.write_state("watching")
            time.sleep(poll_s)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--log-dir", default=None, help="per-run logs (default logs/study2/<group>)")
    ap.add_argument("--launcher-log", default=None)
    ap.add_argument("--poll", type=float, default=5.0)
    a = ap.parse_args(argv)
    w = StopWatch(out_root=Path(a.out_root), group=a.group, log_dir=Path(a.log_dir or ROOT / "logs" / "study2" / a.group),
                  launcher_log=Path(a.launcher_log) if a.launcher_log else None)
    print(json.dumps({"started": w.started.isoformat(), "pid": os.getpid(), "rules": RULES}), flush=True)
    print(w.run(a.poll), flush=True)


if __name__ == "__main__":
    main()
