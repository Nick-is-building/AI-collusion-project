"""Move superseded Study 2 run directories to a sibling group, keeping relative paths (A05b, Nick).

For each given sequence and arm, every run subdirectory results/study2/<group>/repNNN/<arm>/<run_dir>
moves to results/study2/<to-group>/repNNN/<arm>/<run_dir>. Nothing is deleted or rewritten; file
contents (including study2_meta.json, whose resume_from paths still name the old location) are
unchanged. Refuses if any run_arm process is alive, if a destination exists, or if a run is marked
running with a live process. An append-only `superseded_moved` event (list of moved directories) is
added to the source group's scheduler.jsonl; the destination group gets a README.

    PYTHONPATH=. .venv/bin/python -m scripts.study2.supersede --group main --to-group main_superseded \
        --seqs 14-45 --arm Cprime --reason "..." [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts.study2.launch import parse_seqs
from src.hysteresis.scheduler import EXPECTED

README = """# Superseded Study 2 runs (moved from group `{group}`)

Moved by `scripts/study2/supersede.py` on {at} under assignment A05b (`assignments/A05b_study2_relaunch.md`).
Reason: {reason}
Same relative paths as in `results/study2/{group}/`. Nothing was deleted or edited; `study2_meta.json`
files keep their original `resume_from` paths (which name the old location). These runs are never analysed.
"""


def run_arm_alive() -> list[str]:
    out = subprocess.run(["pgrep", "-af", "src.hysteresis.run_arm"], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if "pgrep" not in l]


def plan_moves(src_group: Path, dst_group: Path, seqs: list[int], arm: str) -> list[tuple[Path, Path]]:
    moves = []
    for seq in seqs:
        d = src_group / f"rep{seq:03d}" / arm
        if not d.exists():
            continue
        for run_dir in sorted(p for p in d.iterdir() if p.is_dir()):
            moves.append((run_dir, dst_group / run_dir.relative_to(src_group)))
    return moves


def supersede(out_root: Path, group: str, to_group: str, seqs: list[int], arm: str, reason: str,
              dry_run: bool = False, check_processes: bool = True) -> dict:
    if arm not in EXPECTED:
        raise SystemExit(f"unknown arm {arm!r}")
    if not reason.strip():
        raise SystemExit("--reason is required")
    if check_processes and (alive := run_arm_alive()):
        raise SystemExit(f"refusing: run_arm processes alive: {alive[:3]}")
    src, dst = Path(out_root) / group, Path(out_root) / to_group
    moves = plan_moves(src, dst, seqs, arm)
    clash = [str(b) for _, b in moves if b.exists()]
    if clash:
        raise SystemExit(f"refusing: destinations exist: {clash[:3]}")
    if dry_run:
        return {"dry_run": True, "n": len(moves), "moves": [str(a.relative_to(src)) for a, _ in moves]}
    at = datetime.now(timezone.utc).isoformat()
    dst.mkdir(parents=True, exist_ok=True)
    readme = dst / "README.md"
    if not readme.exists():
        readme.write_text(README.format(group=group, at=at, reason=reason))
    for a, b in moves:
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(a), str(b))       # same filesystem: a rename, contents untouched
    rel = [str(a.relative_to(src)) for a, _ in moves]
    with open(src / "scheduler.jsonl", "a") as fh:
        fh.write(json.dumps({"at": at, "event": "superseded_moved", "to_group": to_group, "arm": arm,
                             "seqs": seqs, "reason": reason, "n": len(rel), "run_dirs": rel}) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return {"dry_run": False, "n": len(rel), "moves": rel}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--to-group", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    r = supersede(Path(a.out_root), a.group, a.to_group, parse_seqs(a.seqs), a.arm, a.reason, a.dry_run)
    print(json.dumps({k: v for k, v in r.items() if k != "moves"}), f"first: {r['moves'][:2]}")


if __name__ == "__main__":
    main()
