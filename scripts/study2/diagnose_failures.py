"""Operational diagnosis of the Study 2 main-run failures (no API call, no outcome).

Reads only: scheduler.jsonl, study2_meta.json, the usage journals (llm_usage.jsonl), the error lines
of the per-run logs, and the project ledger. It never opens a message, verdict or strict_full value;
`episodes` comes from run_arm's metadata (count of persisted episodes).

    PYTHONPATH=. .venv/bin/python -m scripts.study2.diagnose_failures [--group main] [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from src.hysteresis.guard import JournalLedger
from src.runner.costs import Ledger

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {"prefix": 5, "Aprime": 10, "B": 10, "Cprime": 10, "PC": 10}
ERR_PATTERNS = {
    "spend_cap": "exceeded its monthly spending cap",
    "quota_429": "You exceeded your current quota",
    "content_filter": "content policy retry",
}


def log_errors(log: Path) -> dict:
    out = collections.Counter()
    if not log.exists():
        return {"missing_log": 1}
    for line in log.read_text(errors="replace").splitlines():
        if "[LLM error" in line or "[content policy retry" in line:
            for k, pat in ERR_PATTERNS.items():
                if pat in line:
                    out[k] += 1
    return dict(out)


def runs(group_dir: Path):
    for meta_path in sorted(group_dir.glob("rep*/*/*/study2_meta.json")):
        meta = json.loads(meta_path.read_text())
        statuses = collections.Counter()
        times = []
        j = meta_path.parent / "llm_usage.jsonl"
        if j.exists():
            for line in j.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    statuses[r["response_status"]] += 1
                    if r["response_status"] == "accepted":
                        times.append(r["recorded_at"])
        yield {
            "seq": meta["seq"], "arm": meta["arm"], "run_dir": meta["run_dir"],
            "started_at": meta.get("started_at"), "finished_at": meta.get("finished_at"),
            "status": (meta.get("status") or "")[:60], "episodes": meta.get("episodes"),
            "resume_from": Path(meta["resume_from"]).parent.name if meta.get("resume_from") else "",
            "resume_from_episodes": meta.get("resume_from_episodes"),
            "git_head": meta.get("git_head"), "study2_code_dirty": meta.get("study2_code_dirty"),
            "config_sha256": meta.get("config_sha256"),
            "journal_status": dict(statuses),
            "first_accepted": min(times) if times else None, "last_accepted": max(times) if times else None,
        }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="main")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    gdir = ROOT / "results" / "study2" / a.group

    events = [json.loads(l) for l in (gdir / "scheduler.jsonl").read_text().splitlines() if l.strip()]
    launches = {}
    for e in events:
        if e["event"] == "launch":
            launches[e["log"]] = e
    exits = collections.Counter((e["arm"], e["rc"]) for e in events if e["event"] == "exit")
    end = [e for e in events if e["event"] == "scheduler_end"]

    allruns = list(runs(gdir))
    # error classes per launch log
    log_err = {}
    for e in events:
        if e["event"] == "launch":
            log_err[(e["seq"], e["arm"], e["attempt"])] = log_errors(Path(e["log"]))

    # global accepted-call gaps > 5 min
    stamps = []
    for j in gdir.glob("rep*/*/*/llm_usage.jsonl"):
        for line in j.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r["response_status"] == "accepted":
                    stamps.append(r["recorded_at"])
    stamps.sort()
    from datetime import datetime
    gaps = [(x, y) for x, y in zip(stamps, stamps[1:])
            if (datetime.fromisoformat(y) - datetime.fromisoformat(x)).total_seconds() > 300]

    # counted runs: earliest-started complete run per arm (scheduler rule)
    by_arm = collections.defaultdict(list)
    for r in allruns:
        by_arm[(r["seq"], r["arm"])].append(r)
    counted = {}
    for k, rs in by_arm.items():
        done = [r for r in rs if (r["episodes"] or 0) >= EXPECTED[k[1]] and r["status"] == "complete"]
        if done:
            counted[k] = min(done, key=lambda r: r["started_at"])
    incomplete = sorted(k for k in by_arm if k not in counted)
    multi = {f"{k[0]}:{k[1]}": [(r["run_dir"][-6:], r["episodes"], r["status"][:30], r["resume_from"][-6:])
                                for r in sorted(rs, key=lambda r: r["started_at"])]
             for k, rs in sorted(by_arm.items()) if len(rs) > 1}

    led = JournalLedger(ROOT / "results" / "study2").refresh()
    s2 = led.by_group()
    project_other = Ledger(ROOT / "results" / "raw", mode="live").total

    out = {
        "scheduler_end": end[-1] if end else None,
        "exits_by_arm_rc": {f"{a}:{rc}": n for (a, rc), n in sorted(exits.items())},
        "runs_total": len(allruns),
        "arms_complete": len(counted), "arms_incomplete": [f"{s}:{a}" for s, a in incomplete],
        "accepted_call_gaps_gt_5min": gaps,
        "arms_with_more_than_one_run": multi,
        "launch_error_classes": {f"{s}:{a}:{n}": v for (s, a, n), v in sorted(log_err.items()) if v},
        "counted_runs_with_errors_in_journal": {
            f"{k[0]}:{k[1]}": r["journal_status"] for k, r in sorted(counted.items())
            if set(r["journal_status"]) - {"accepted"}},
        "counted_runs_spanning_gap": [f"{k[0]}:{k[1]}" for k, r in sorted(counted.items())
                                      for g0, g1 in gaps if r["started_at"] < g1 and (r["finished_at"] or "") > g0],
        "counted_git_heads": dict(collections.Counter(r["git_head"] for r in counted.values())),
        "counted_code_dirty": sum(bool(r["study2_code_dirty"]) for r in counted.values()),
        "counted_caps_sha": dict(collections.Counter(r["config_sha256"]["configs/caps.yaml"] for r in counted.values())),
        "spend_usd": {"study2_by_group": {g: round(v, 4) for g, v in s2.items()},
                      "study2_total": round(led.total, 4),
                      "project_other_results_raw": round(project_other, 4),
                      "project_total": round(led.total + project_other, 4)},
        "spend_failed_arms_usd": round(sum(
            led.record_cost(json.loads(l)) for (s, a) in incomplete
            for j in (gdir / f"rep{s:03d}" / a).glob("*/llm_usage.jsonl")
            for l in j.read_text().splitlines() if l.strip()), 4),
    }
    txt = json.dumps(out, indent=1, default=str)
    print(txt)
    if a.json:
        Path(a.json).write_text(txt + "\n")


if __name__ == "__main__":
    main()
