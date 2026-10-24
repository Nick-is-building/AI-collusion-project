"""Export the committed record of a Study 2 group (D27, Nick): derived per-call table, per-file hashes,
and a run manifest. The full traces (run.json, usage journals, controlled-Bob caches) stay on the
machine and are uploaded as a Hugging Face dataset before submission (separate assignment).

Writes, under results/study2/<group>/ (committed):
  manifest.csv     one row per run directory: seq, arm, run_dir, status, episodes, started/finished,
                   git_head, counted (the run that counts: earliest-started complete run), resume source
  files_sha256.txt SHA-256 and size of every file under the group (run.json, llm_usage.jsonl,
                   study2_meta.json, bob_cache/*), as `sha256  bytes  path`
  calls.csv.gz     one row per API request from the usage journals: seq, arm, run_dir, episode_index,
                   actor, phase, round, attempt, response_status, error_category, response_model,
                   input/cached/output/billable tokens, cost_usd (our price table), recorded_at
Operational fields only: no message, verdict or outcome is exported here. Field values are as recorded
by upstream's usage journal (e.g. its episode_index numbering), unchanged.

    PYTHONPATH=. .venv/bin/python -m scripts.study2.export --group main --seqs 1-50
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from scripts.study2.launch import parse_seqs
from src.hysteresis.guard import JOURNAL
from src.hysteresis.scheduler import EXPECTED, scan
from src.runner.costs import PriceTable

CALL_FIELDS = ("episode_index", "actor", "phase", "round_idx", "attempt_idx", "api_attempt", "response_status",
               "error_category", "response_model", "requested_model", "input_tokens", "cached_input_tokens",
               "output_tokens", "reasoning_tokens", "billable_output_tokens", "recorded_at")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export(out_root: Path, group: str, seqs: list[int]) -> dict:
    gdir = Path(out_root) / group
    prices = PriceTable()
    manifest, n_calls = [], 0
    with gzip.open(gdir / "calls.csv.gz", "wt", newline="") as gz:
        w = csv.writer(gz)
        w.writerow(["seq", "arm", "run_dir", *CALL_FIELDS, "cost_usd"])
        for seq in seqs:
            for arm in EXPECTED:
                st = scan(gdir, seq, arm)
                counted = st.complete_run()
                for run_json, eps, meta in sorted(st.runs, key=lambda r: r[2].get("started_at", "")):
                    d = run_json.parent
                    manifest.append({"seq": seq, "arm": arm, "run_dir": d.name, "status": meta.get("status"),
                                     "episodes": eps, "started_at": meta.get("started_at"),
                                     "finished_at": meta.get("finished_at"), "git_head": meta.get("git_head"),
                                     "counted": run_json == counted,
                                     "resume_from_run_dir": Path(meta["resume_from"]).parent.name
                                     if meta.get("resume_from") else ""})
                    j = d / JOURNAL
                    if not j.exists():
                        continue
                    for line in j.read_text().splitlines():
                        if not line.strip():
                            continue
                        r = json.loads(line)
                        cost = prices.usage_cost(r["requested_model"], r) if r.get("input_tokens") else 0.0
                        w.writerow([seq, arm, d.name, *[r.get(k) for k in CALL_FIELDS], round(cost, 8)])
                        n_calls += 1
    with open(gdir / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0]) if manifest else ["seq"])
        w.writeheader()
        w.writerows(manifest)
    files = sorted(p for p in gdir.rglob("*") if p.is_file() and p.name not in
                   ("calls.csv.gz", "manifest.csv", "files_sha256.txt", "runs.csv"))
    with open(gdir / "files_sha256.txt", "w") as fh:
        for p in files:
            fh.write(f"{sha256(p)}  {p.stat().st_size}  {p.relative_to(gdir)}\n")
    return {"runs": len(manifest), "calls": n_calls, "files_hashed": len(files)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--seqs", required=True)
    ap.add_argument("--out-root", default="results/study2")
    a = ap.parse_args(argv)
    print(json.dumps(export(Path(a.out_root), a.group, parse_seqs(a.seqs))))


if __name__ == "__main__":
    main()
