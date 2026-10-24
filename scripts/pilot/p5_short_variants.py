"""P5 short variants (plan section 10; A03 task 4): R4, R4n, R5, R6 on 5 items, both versions (40 calls).

Items: src.runner.item_lists.p5_items() (5 hold-out items with a validated bait, seed 2026; no main item
is touched). Pass (plan 10): the variants run; reported per variant: completed / missing, verdicts per
version, R5 API input tokens vs the matched countTokens value, R6 gate outcomes.

  .venv/bin/python -m scripts.pilot.p5_short_variants [--plan] [--live --approved-stage pilot] [--workers N]
      [--r6-only]

--r6-only (A04 task 1): rerun of the R6 part after D13 (data-search wording, verdict-prompt sentence);
check name P5-R6-D13 (own call IDs, so the A03 P5 calls are not resumed into it), 10 calls,
check-group cap a04_p5_r6 = 0.30 USD (configs/caps.yaml).
"""
from scripts.pilot.common import execute_parallel, parser, read_calls
from src.runner.item_lists import p5_items
from src.runner.jobs import make_job

VARIANTS = ("R4", "R4n", "R5", "R6")
R6_CHECK = "P5-R6-D13"


def jobs():
    return [make_job("P5", r, v, s) for r in p5_items().itertuples() for v in VARIANTS for s in ("bait", "correct")]


def jobs_r6():
    return [make_job(R6_CHECK, r, "R6", s) for r in p5_items().itertuples() for s in ("bait", "correct")]


def evaluate(paths, check="P5"):
    import pandas as pd
    from src.runner.jobs import R5_TABLE
    calls = [c for p in paths for c in read_calls(p) if c["check"] == check]
    r5 = pd.read_csv(R5_TABLE).set_index(["item_id", "version"])
    out = {"calls": len(calls), "missing": sum(c["verdict_status"] != "ok" for c in calls)}
    for v in VARIANTS:
        sub = [c for c in calls if c["variant"] == v]
        out[v] = {s: [c["verdict"] for c in sub if c["version"] == s] for s in ("bait", "correct")}
    r5c = []
    for c in calls:
        if c["variant"] == "R5":
            acc = [u for u in c["usage"] if u.get("response_status") == "accepted"]
            r5c.append(dict(item=c["item_id"], version=c["version"], api=acc[0]["input_tokens"] if acc else None,
                            counted=int(r5.loc[(c["item_id"], c["version"]), "count_R5"])))
    out["R5_tokens"] = r5c
    r6 = lambda c: (c.get("extra") or {}).get("r6", {})   # noqa: E731
    out["R6"] = [dict(item=c["item_id"], version=c["version"], **{k: r6(c).get(k) for k in
                 ("first_verdict", "gate_fired", "retry_verdict", "final_verdict")},
                      first_present=(r6(c).get("first_check") or {}).get("present"),
                      first_compliant=(r6(c).get("first_check") or {}).get("compliant"),
                      retry_compliant=(r6(c).get("retry_check") or {}).get("compliant"))
                 for c in calls if c["variant"] == "R6"]
    return out


def main(argv=None):
    ap = parser("P5 short variants")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--r6-only", action="store_true", help="A04 task 1: R6 rerun after D13")
    args = ap.parse_args(argv)
    if args.r6_only:
        stats = execute_parallel("P5 R6 rerun (D13)", "scripts.pilot.p5_short_variants:jobs_r6", jobs_r6(), args)
    else:
        stats = execute_parallel("P5 short variants", "scripts.pilot.p5_short_variants:jobs", jobs(), args)
    if stats:
        import json
        print(json.dumps(evaluate([s["run_path"] for s in stats], R6_CHECK if args.r6_only else "P5"), indent=1))
    return stats


if __name__ == "__main__":
    main()
