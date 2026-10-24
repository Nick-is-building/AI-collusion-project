"""P3 edited histories (plan section 10): the API accepts the cut, R2 and R3 contexts.

5 pilot hold-out items, rng = default_rng(2026) (fresh generator; independent of P2's draw), drawn
without replacement from the hold-out sorted by item_id; each runs CUT (= R0'), R2 and R3 on the
correct version = 15 calls. Pass: no call ends in an API error (status "missing" with a 4xx error).

  .venv/bin/python -m scripts.pilot.p3_edited_histories [--plan]
"""
from scripts.pilot.common import execute, holdout, make_job, parser, read_calls, rng


def items():
    h = holdout()
    ids = rng().choice(h.item_id.tolist(), size=min(5, len(h)), replace=False)
    return h.set_index("item_id").loc[list(ids)].reset_index()


def jobs():
    return [make_job("P3", r, v) for r in items().itertuples() for v in ("R0p", "R2", "R3")]


def evaluate(path):
    calls = [c for c in read_calls(path) if c["check"] == "P3"]
    errors = [c["call_id"] for c in calls if c["status"] != "complete"]
    return dict(n=len(calls), api_errors=len(errors), passed=len(calls) == 15 and not errors, failed=errors)


def main(argv=None):
    args = parser("P3 edited histories").parse_args(argv)
    stats = execute("P3 edited histories", jobs(), args)
    if stats:
        print("P3 evaluation:", evaluate(stats["run_path"]))
    return stats


if __name__ == "__main__":
    main()
