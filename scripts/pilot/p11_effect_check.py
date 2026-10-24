"""P11 effect check (plan section 10; scheduling only, never confirmatory): R1 and R4 on the bait
versions of all pilot hold-out items (20) = 40 calls.

Bait content is read from data/derived/baits/<item_id>.json (field "bob_r1_content", task 6).
Items without a bait file are reported; if none exists the check is blocked (plan printed only).

  .venv/bin/python -m scripts.pilot.p11_effect_check [--plan]
"""
from scripts.pilot.common import execute, holdout, load_bait, make_job, parser


def jobs():
    out, missing = [], []
    for r in holdout().itertuples():
        b = load_bait(r.item_id)
        if b is None:
            missing.append(r.item_id)
            continue
        out += [make_job("P11", r, v, version="bait", bob_r1_content=b) for v in ("R1", "R4")]
    return out, missing


def planned_jobs():
    """The 40 jobs as they will be, with correct-version content (for projection only)."""
    return [make_job("P11", r, v, version="bait") for r in holdout().itertuples() for v in ("R1", "R4")]


def main(argv=None):
    args = parser("P11 effect check").parse_args(argv)
    js, missing = jobs()
    if missing:
        print(f"P11: baits missing for {len(missing)} of {len(holdout())} hold-out items")
    if not js:
        print("P11: blocked: baits not built")
        from scripts.pilot.common import report_plan
        report_plan("P11 effect check (projected, baits not built)", planned_jobs())
        return None
    return execute("P11 effect check", js, args)


if __name__ == "__main__":
    main()
