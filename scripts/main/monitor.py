"""Operational monitor for the main run (A04 task 3; plan 23.3; D18).

Reads results/raw/main-*.jsonl and prints ONLY operational figures: calls completed / expected per
variant, missing verdicts (missing_error, missing_forced) per variant, API error and 429 counts,
response_model values, spend against the stage cap, run_start / run_end lines, wall time.
It prints no verdict, detection, or rejection figure (D18: no outcome analysis before the
natural-error rubric is committed).

  .venv/bin/python -m scripts.main.monitor
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(results_dir=ROOT / "results" / "raw", prefix="main-"):
    calls, runs = [], []
    for p in sorted(Path(results_dir).glob(f"{prefix}*.jsonl")):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            (calls if r.get("type") == "call" else runs).append(r)
    return calls, runs


def summary(calls, runs, expected=None, cap=None) -> dict:
    exp = collections.Counter(c.split(":")[3] for c in expected) if expected else {}
    by = collections.defaultdict(collections.Counter)
    errs, models = collections.Counter(), collections.Counter()
    for c in calls:
        v = by[c["variant"]]
        v["done"] += 1
        v[c["verdict_status"]] += 1
        for k, n in (c.get("api_error_counts") or {}).items():
            errs[k] += n
        errs["n_rate_limit"] += c.get("n_rate_limit") or 0
        for m in c.get("response_models") or []:
            models[m] += 1
    spend = sum(c.get("cost_usd") or 0 for c in calls)
    ts = sorted(c["ts_end_utc"] for c in calls if c.get("ts_end_utc"))
    return dict(calls=len(calls), unique_call_ids=len({c["call_id"] for c in calls}), expected=sum(exp.values()) or None,
                per_variant={k: dict(v, expected=exp.get(k)) for k, v in sorted(by.items())},
                api_errors=dict(errs), response_models=dict(models), spend_usd=round(spend, 4), cap_usd=cap,
                first_end=ts[0] if ts else None, last_end=ts[-1] if ts else None,
                runs=[{k: r.get(k) for k in ("type", "run_id", "git_commit", "git_dirty", "completed", "missing", "stopped")}
                      for r in runs])


def main():
    import yaml
    ids = (ROOT / "data" / "derived" / "prereg" / "main_run_call_ids.txt").read_text().split()
    cap = yaml.safe_load((ROOT / "configs" / "caps.yaml").read_text())["stages"].get("main")
    calls, runs = read()
    print(json.dumps(summary(calls, runs, ids, cap), indent=1))


if __name__ == "__main__":
    main()
