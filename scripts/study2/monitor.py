"""Operational monitor for Study 2 runs (plan 23.3). It reports no outcome.

Reads only the upstream usage journals (`llm_usage.jsonl`) and the run metadata of one group:
calls, error categories, rate-limit errors (429), response models, spend with our price table,
cached share of input tokens, throughput, wall time, and run states. It never opens channel
messages, verdicts, or strict_full (no outcome before the run is complete; D21, A05 task 6).

    PYTHONPATH=. .venv/bin/python -m scripts.study2.monitor --group main [--seqs 1-50] [--json]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from src.hysteresis.guard import JOURNAL
from src.hysteresis.scheduler import EXPECTED, scan
from src.runner.costs import PriceTable

# Upstream median calls per arm in Shi's unconstrained traces (docs/study2_implementation_plan.md);
# used only to project spend from progress. PC counts Alice's calls only.
EXPECTED_CALLS = {"prefix": 115, "Aprime": 115, "B": 115, "Cprime": 230, "PC": 58}
RATE_LIMIT_CATEGORIES = {"transient_rate_limit", "hard_quota"}


def journal_records(group_dir: Path):
    for f in sorted(group_dir.rglob(JOURNAL)):
        arm = f.parent.parent.name
        for line in f.read_text().splitlines():
            if line.strip():
                try:
                    yield arm, json.loads(line)
                except ValueError:
                    continue


def summarize(group_dir: Path, seqs: list[int] | None = None, prices: PriceTable | None = None) -> dict:
    prices = prices or PriceTable()
    calls = Counter()
    statuses, errors, models = Counter(), Counter(), Counter()
    cost, cost_by_arm = 0.0, Counter()
    inp = cached = 0
    times = []
    for arm, r in journal_records(group_dir):
        calls[arm] += 1
        statuses[r.get("response_status")] += 1
        if r.get("error_category"):
            errors[r["error_category"]] += 1
        if r.get("response_status") == "accepted":
            models[r.get("response_model")] += 1
        if r.get("input_tokens"):
            c = prices.usage_cost(r["requested_model"], r)
            cost += c
            cost_by_arm[arm] += c
            inp += r["input_tokens"]
            cached += r.get("cached_input_tokens") or 0
        if r.get("recorded_at"):
            times.append(datetime.fromisoformat(r["recorded_at"]))
    times.sort()
    recent = [t for t in times if times and t > times[-1] - timedelta(minutes=5)]
    out = {
        "calls": sum(calls.values()), "calls_by_arm": dict(calls),
        "response_status": dict(statuses), "error_categories": dict(errors),
        "rate_limit_errors": sum(v for k, v in errors.items() if k in RATE_LIMIT_CATEGORIES),
        "response_models": dict(models),
        "cost_usd": round(cost, 4), "cost_by_arm": {k: round(v, 4) for k, v in cost_by_arm.items()},
        "input_tokens": inp, "cached_input_tokens": cached,
        "cached_share": round(cached / inp, 4) if inp else None,
        "first_call": times[0].isoformat() if times else None, "last_call": times[-1].isoformat() if times else None,
        "wall_minutes": round((times[-1] - times[0]).total_seconds() / 60, 1) if times else 0.0,
        "calls_per_min_last5": round(len(recent) / 5, 1) if recent else 0.0,
    }
    if seqs:
        states = {(s, a): scan(group_dir, s, a) for s in seqs for a in EXPECTED}
        out["arms_complete"] = sum(st.complete for st in states.values())
        out["arms_total"] = len(states)
        out["arms_running"] = sum(1 for st in states.values() if st.runs and not st.complete
                                  and st.best[2].get("status") == "running")
        out["arms_failed_attempts"] = sum(1 for st in states.values() for _, _, m in st.runs
                                          if str(m.get("status", "")).startswith("failed"))
        expected_calls = sum(EXPECTED_CALLS[a] for (_, a) in states)
        out["projected_cost_usd"] = round(cost * expected_calls / out["calls"], 2) if out["calls"] else None
    return out


def main(argv=None):
    from scripts.study2.launch import parse_seqs
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True)
    ap.add_argument("--out-root", default="results/study2")
    ap.add_argument("--seqs", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    s = summarize(Path(a.out_root) / a.group, parse_seqs(a.seqs) if a.seqs else None)
    if a.json:
        print(json.dumps(s, indent=1))
    else:
        for k, v in s.items():
            print(f"{k}: {v}")
    stop = Path(a.out_root) / "STOP"
    if stop.exists():
        print("STOP FILE PRESENT:", stop.read_text().strip())


if __name__ == "__main__":
    main()
