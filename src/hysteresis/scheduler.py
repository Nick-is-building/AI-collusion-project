"""Study 2 scheduler: one upstream process per (sequence, arm), resumable, state read from disk.

Order constraints (plan 9.1): A' and B start after the sequence's prefix is complete; the partner
control starts after the sequence's B run is complete (B before PC within each sequence). C' and
the prefix start at once. Launch priority (critical path prefix -> B -> PC first):
B, PC, prefix, C', A', then by sequence number.

Run state comes from the run directories (`study2_meta.json`, `run.json`), never from memory, so a
restarted scheduler continues where it stopped (plan 23.2):
  - complete: a run.json with the arm's full episode count (prefix 5, others 10);
  - partial: the best run.json has fewer episodes; the next launch resumes from it with
    --resume-from (upstream resumes at episode boundaries, always into a new run directory). A
    branch or C' with nothing beyond its source restarts from the source (prefix / fresh);
  - an arm gets at most MAX_ATTEMPTS launches; after that it is marked failed and not relaunched.
    Plan 9.2 says a technically failed trajectory is rerun in all arms; that decision is left to
    the operator and reported, not automated.
Concurrency: `--workers`, overridable while running through the file <group dir>/WORKERS (D23 ramp
8 -> 16 -> 32 only while 429s stay at zero; the scheduler never ramps by itself). A STOP file in
the results root (model change, operator) blocks new launches; running processes stop at their
next call (src/hysteresis/guard.py). Every launch and exit is appended to <group dir>/scheduler.jsonl.
Parallelism changes no run's content: each run is its own process with its own history.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {"prefix": 5, "Aprime": 10, "B": 10, "Cprime": 10, "PC": 10}
PRIORITY = ("B", "PC", "prefix", "Cprime", "Aprime")
MAX_ATTEMPTS = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def episodes_of(run_json: Path) -> int:
    try:
        return len(json.loads(Path(run_json).read_text())["results"])
    except (OSError, ValueError, KeyError):
        return 0


def pid_alive(meta: dict) -> bool:
    if meta.get("status") != "running" or not meta.get("pid"):
        return False
    try:
        return b"src.hysteresis.run_arm" in Path(f"/proc/{int(meta['pid'])}/cmdline").read_bytes()
    except (OSError, ValueError):
        return False


def finished(run) -> bool:
    """All episodes persisted and the process has ended (B must be finished before PC)."""
    path, eps, meta = run
    return eps > 0 and not pid_alive(meta)


@dataclass
class ArmState:
    seq: int
    arm: str
    runs: list = field(default_factory=list)   # (run.json path, episodes, meta dict)

    @property
    def best(self):
        return max(self.runs, key=lambda r: (r[1], r[2].get("started_at", ""))) if self.runs else None

    @property
    def complete(self) -> bool:
        return any(r[1] >= EXPECTED[self.arm] and finished(r) for r in self.runs)

    @property
    def attempts(self) -> int:
        return len(self.runs)

    def alive_elsewhere(self) -> bool:
        """A run of this arm still marked running whose process is alive (e.g. launched by an
        earlier scheduler instance): never launch a second one beside it."""
        return any(pid_alive(meta) for _, _, meta in self.runs)

    def complete_run(self) -> Path | None:
        """The run that counts: the earliest-started complete run (a rule that does not depend on
        any outcome; duplicates should not occur, see Scheduler.orphans)."""
        done = [r for r in self.runs if r[1] >= EXPECTED[self.arm] and finished(r)]
        return min(done, key=lambda r: r[2].get("started_at", ""))[0] if done else None


def scan(group_dir: Path, seq: int, arm: str) -> ArmState:
    st = ArmState(seq, arm)
    for meta_path in sorted((group_dir / f"rep{seq:03d}" / arm).glob("*/study2_meta.json")):
        meta = json.loads(meta_path.read_text())
        run_json = meta_path.parent / "run.json"
        st.runs.append((run_json, episodes_of(run_json), meta))
    return st


class Scheduler:
    def __init__(self, *, out_root: Path, group: str, seqs: list[int], workers: int, backend: str,
                 approved_stage: str | None = None, reserve_slots: int | None = None, log_dir: Path | None = None,
                 extra_env: dict | None = None, poll_s: float = 5.0, python: str = sys.executable):
        self.out_root = Path(out_root).resolve()
        self.group = group
        self.group_dir = self.out_root / group
        self.group_dir.mkdir(parents=True, exist_ok=True)
        self.seqs = seqs
        self.workers = workers
        self.backend = backend
        self.approved_stage = approved_stage
        self.reserve_slots = reserve_slots
        self.log_dir = Path(log_dir or ROOT / "logs" / "study2" / group)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.env = {**os.environ, "PYTHONPATH": str(ROOT), **(extra_env or {})}
        self.poll_s = poll_s
        self.python = python
        self.running: dict[tuple[int, str], subprocess.Popen] = {}
        self.events = self.group_dir / "scheduler.jsonl"

    def log(self, **rec):
        with open(self.events, "a") as fh:
            fh.write(json.dumps({"at": utc_now(), **rec}) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def current_workers(self) -> int:
        f = self.group_dir / "WORKERS"
        try:
            return max(int(f.read_text().strip()), 0)
        except (OSError, ValueError):
            return self.workers

    def state(self) -> dict[tuple[int, str], ArmState]:
        return {(s, a): scan(self.group_dir, s, a) for s in self.seqs for a in EXPECTED}

    def command(self, st: ArmState, states) -> list[str] | None:
        """The run_arm command for the next launch of this arm, or None if not ready."""
        prefix = states[(st.seq, "prefix")]
        resume = ""
        if st.arm in ("Aprime", "B", "PC"):
            if not prefix.complete or (st.seq, "prefix") in self.running:
                return None
            resume = str(prefix.complete_run())
        b_run = ""
        if st.arm == "PC":
            b = states[(st.seq, "B")]
            if not b.complete or (st.seq, "B") in self.running:
                return None
            b_run = str(b.complete_run())
        if st.runs:
            path, eps, _ = st.best
            floor = 5 if st.arm in ("Aprime", "B", "PC") else 0
            if eps > floor:
                resume = str(path)
        cmd = [self.python, "-m", "src.hysteresis.run_arm", "--arm", st.arm, "--seq", str(st.seq),
               "--out-root", str(self.out_root), "--group", self.group, "--backend", self.backend,
               "--reserve-slots", str(self.reserve_slots or self.current_workers())]
        if resume:
            cmd += ["--resume-from", resume]
        if b_run:
            cmd += ["--b-run", b_run]
        if self.approved_stage:
            cmd += ["--approved-stage", self.approved_stage]
        return cmd

    def reap(self):
        for key, p in list(self.running.items()):
            rc = p.poll()
            if rc is not None:
                self.log(event="exit", seq=key[0], arm=key[1], pid=p.pid, rc=rc)
                del self.running[key]

    def orphans(self) -> set:
        """(seq, arm) launched by an earlier scheduler instance (launch event without exit event)
        whose process is still a live run_arm process. Covers the window before a child has written
        its study2_meta.json."""
        if not self.events.exists():
            return set()
        launched = {}
        for line in self.events.read_text().splitlines():
            ev = json.loads(line)
            if ev.get("event") == "launch":
                launched[ev["pid"]] = (ev["seq"], ev["arm"])
            elif ev.get("event") == "exit":
                launched.pop(ev["pid"], None)
        out = set()
        for pid, key in launched.items():
            if key in self.running:
                continue
            try:
                if b"src.hysteresis.run_arm" in Path(f"/proc/{pid}/cmdline").read_bytes():
                    out.add(tuple(key))
            except OSError:
                continue
        return out

    def stopped(self) -> bool:
        return (self.out_root / "STOP").exists()

    def step(self) -> dict:
        """Reap, then launch ready arms up to the worker limit. Returns a status summary."""
        self.reap()
        states = self.state()
        done = sum(st.complete for st in states.values())
        failed = [k for k, st in states.items() if not st.complete and st.attempts >= MAX_ATTEMPTS
                  and k not in self.running]
        if self.stopped():
            return {"done": done, "total": len(states), "running": len(self.running), "failed": failed,
                    "stopped": True}
        orphans = self.orphans()
        order = sorted(states.values(), key=lambda s: (PRIORITY.index(s.arm), s.seq))
        for st in order:
            if len(self.running) >= self.current_workers():
                break
            key = (st.seq, st.arm)
            if (st.complete or key in self.running or key in orphans or st.attempts >= MAX_ATTEMPTS
                    or st.alive_elsewhere()):
                continue
            cmd = self.command(st, states)
            if cmd is None:
                continue
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            log_path = self.log_dir / f"rep{st.seq:03d}_{st.arm}_{ts}.log"
            with open(log_path, "w") as fh:
                p = subprocess.Popen(cmd, cwd=ROOT, env=self.env, stdout=fh, stderr=subprocess.STDOUT)
            self.running[key] = p
            self.log(event="launch", seq=st.seq, arm=st.arm, pid=p.pid, attempt=st.attempts + 1,
                     cmd=cmd[2:], log=str(log_path))
        return {"done": done, "total": len(states), "running": len(self.running), "failed": failed,
                "stopped": False}

    def run(self) -> dict:
        self.log(event="scheduler_start", seqs=self.seqs, workers=self.workers, backend=self.backend)
        while True:
            s = self.step()
            if not self.running and not self.orphans() and (s["stopped"] or s["done"] + len(s["failed"]) >= s["total"]
                                     or not self._launchable()):
                self.log(event="scheduler_end", **{k: v for k, v in s.items() if k != "failed"},
                         failed=[list(k) for k in s["failed"]])
                return s
            time.sleep(self.poll_s)

    def _launchable(self) -> bool:
        states = self.state()
        return any(not st.complete and st.attempts < MAX_ATTEMPTS and self.command(st, states) is not None
                   for st in states.values())
