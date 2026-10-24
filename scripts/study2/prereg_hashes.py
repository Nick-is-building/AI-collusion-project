"""SHA-256 table of the files PREREGISTRATION_STUDY2.md freezes (printed as Markdown rows).

Hashes are taken from the committed blobs at a revision (default HEAD), not from the working tree:
another session may hold uncommitted edits to shared files (e.g. configs/caps.yaml).

    PYTHONPATH=. .venv/bin/python -m scripts.study2.prereg_hashes
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN = (
    "PROJECT_PLAN.md",
    "assignments/A05_study2_build_launch.md",
    "docs/deviations.md",
    "configs/caps.yaml",
    "configs/prices.yaml",
    "src/hysteresis/analysis.py",
    "scripts/study2/analyze.py",
    "src/reanalysis/transmission.py",
    "src/hysteresis/run_arm.py",
    "src/hysteresis/status_line.py",
    "src/hysteresis/partner_control.py",
    "src/hysteresis/guard.py",
    "src/hysteresis/scheduler.py",
    "src/hysteresis/upstream_tree.py",
    "scripts/study2/launch.py",
    "scripts/study2/fix_n.py",
    "results/summaries/study2_n.json",
)


def rows(rev: str = "HEAD"):
    for f in FROZEN:
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{f}"], capture_output=True)
        yield f, hashlib.sha256(r.stdout).hexdigest() if r.returncode == 0 else "NOT COMMITTED"


if __name__ == "__main__":
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    print(f"| File (at {rev}) | SHA-256 |\n|---|---|")
    for f, h in rows(rev):
        print(f"| `{f}` | `{h}` |")
