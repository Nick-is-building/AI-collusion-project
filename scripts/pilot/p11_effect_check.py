"""P11 effect check (plan section 10; A03 task 4; scheduling only, never confirmatory): R1 and R4 on the
bait versions of all hold-out items with a validated bait (16 of 20) = 32 calls.

Report (A03): aggregated detection rates only (share of REJECT on bait versions, R1 and R4, overall).
Its result may only change the schedule and the focus of the writing (plan 10).

  .venv/bin/python -m scripts.pilot.p11_effect_check [--plan] [--live --approved-stage pilot] [--workers N]
"""
from scripts.pilot.common import execute_parallel, parser, read_calls
from src.runner.item_lists import holdout_items
from src.runner.jobs import make_job


def jobs():
    return [make_job("P11", r, v, "bait") for r in holdout_items().itertuples() for v in ("R1", "R4")]


def evaluate(paths):
    calls = [c for p in paths for c in read_calls(p) if c["check"] == "P11"]
    out = {"calls": len(calls), "missing": sum(c["verdict_status"] != "ok" for c in calls)}
    for v in ("R1", "R4"):
        ys = [c["verdict"] == "reject" for c in calls if c["variant"] == v and c["verdict_status"] == "ok"]
        out[f"detection_{v}"] = (sum(ys) / len(ys)) if ys else None
        out[f"n_{v}"] = len(ys)
    return out


def main(argv=None):
    ap = parser("P11 effect check")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)
    stats = execute_parallel("P11 effect check", "scripts.pilot.p11_effect_check:jobs", jobs(), args)
    if stats:
        print("P11 (aggregated only):", evaluate([s["run_path"] for s in stats]))
    return stats


if __name__ == "__main__":
    main()
