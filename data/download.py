"""Download Shi et al.'s dataset files used by this project, at the pinned revision.

Source: https://huggingface.co/datasets/SALT-NLP/agent-collusion
Revision: 2eba8f3771e8fbcc0f49f6cbbfd2111b939a117a (PROJECT_PLAN.md section 6). Never `main`.

Files go to data/raw/<repo path> (data/raw/ is git-ignored). SHA-256 of every file is
written to data/checksums.txt (committed). Usage:

    .venv/bin/python data/download.py            # download (skips files already present) + checksums
    .venv/bin/python data/download.py --verify   # only recompute and compare with data/checksums.txt
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

REPO = "SALT-NLP/agent-collusion"
REVISION = "2eba8f3771e8fbcc0f49f6cbbfd2111b939a117a"
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
CHECKSUMS = ROOT / "checksums.txt"
MIN_FREE_BYTES = 2 * 10**9

TRACE_DIR = "traces/communication/communication__gemini-3-1-flash-lite__unconstrained/"
# Agent tables listed in prior_work/1_reanalyse/pruefsummen_reanalyse.txt.
AGENT_TABLES = [
    "data/agents/communication/communication__gemini-3-1-flash-lite__unconstrained.parquet",
    "data/agents/communication/communication__gemini-3-7-flash__unconstrained.parquet",
    "data/agents/main/main__gemini-3-1-flash-lite.parquet",
    "data/agents/main/main__gemini-3-7-flash.parquet",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wanted_files():
    files = HfApi().list_repo_files(REPO, repo_type="dataset", revision=REVISION)
    sel = ["SCHEMA.md", "EXPERIMENTS.md"] + AGENT_TABLES
    sel += sorted(f for f in files if f.startswith(TRACE_DIR))
    sel += sorted(f for f in files if f.startswith("data/episodes/") and f.endswith(".parquet"))
    missing = [f for f in sel if f not in files]
    if missing:
        sys.exit(f"not in revision {REVISION}: {missing}")
    n_traces = sum(f.startswith(TRACE_DIR) for f in sel)
    n_ep = sum(f.startswith("data/episodes/") for f in sel)
    if n_traces != 50 or n_ep != 53:
        sys.exit(f"unexpected file counts: traces={n_traces} (want 50), episode tables={n_ep} (want 53)")
    return sel


def write_checksums(paths):
    lines = [f"# SHA-256 of data/raw/, dataset {REPO} at revision {REVISION}\n"]
    lines += [f"{sha256(RAW / p)}  {p}\n" for p in paths]
    CHECKSUMS.write_text("".join(lines))


def verify():
    bad = 0
    for line in CHECKSUMS.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        digest, path = line.split("  ", 1)
        got = sha256(RAW / path) if (RAW / path).exists() else "MISSING"
        if got != digest:
            bad += 1
            print("MISMATCH", path)
    print("checksums OK" if not bad else f"{bad} mismatches")
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        sys.exit(0 if verify() else 1)
    free = shutil.disk_usage(ROOT).free
    print(f"free disk: {free / 1e9:.1f} GB")
    if free < MIN_FREE_BYTES:
        sys.exit("less than 2 GB free; stopping")
    sel = wanted_files()
    for i, f in enumerate(sel, 1):
        if not (RAW / f).exists():
            hf_hub_download(REPO, f, repo_type="dataset", revision=REVISION, local_dir=RAW)
        if i % 25 == 0:
            print(f"{i}/{len(sel)}")
    write_checksums(sel)
    print(f"{len(sel)} files; checksums written to {CHECKSUMS}")


if __name__ == "__main__":
    main()
