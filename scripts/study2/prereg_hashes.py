"""SHA-256 table of the files PREREGISTRATION_STUDY2.md freezes (printed as Markdown rows).

    PYTHONPATH=. .venv/bin/python -m scripts.study2.prereg_hashes
"""
from __future__ import annotations

import hashlib
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


def rows():
    for f in FROZEN:
        p = ROOT / f
        yield f, hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"


if __name__ == "__main__":
    print("| File | SHA-256 |\n|---|---|")
    for f, h in rows():
        print(f"| `{f}` | `{h}` |")
