"""P2 R0 request identity (plan section 10; fidelity level 1, section 8.7).

R0 (no cut, correct version) on 10 pilot hold-out items: rng = default_rng(2026); 10 item_ids drawn
without replacement from the hold-out sorted by item_id. Pass: the API-reported input_tokens equal
the original verdict call's logged input_tokens in at least 9 of 10 items. `evaluate` reads a run
file; in mock mode the token check is not meaningful (mock tokens are a stand-in).

  .venv/bin/python -m scripts.pilot.p2_r0_identity [--plan]
"""
from scripts.pilot.common import execute, holdout, make_job, parser, read_calls, rng
from src.runner.estimates import r0_tokens


def items():
    h = holdout()
    ids = rng().choice(h.item_id.tolist(), size=min(10, len(h)), replace=False)
    return h.set_index("item_id").loc[list(ids)].reset_index()


def jobs():
    return [make_job("P2", r, "R0") for r in items().itertuples()]


def evaluate(path):
    ref = r0_tokens()
    calls = [c for c in read_calls(path) if c["check"] == "P2"]
    match = 0
    for c in calls:
        acc = [u for u in c["usage"] if u.get("response_status") == "accepted"]
        got = acc[0]["input_tokens"] if acc else None
        match += got == ref[c["item_id"]]
    return dict(n=len(calls), exact_match=match, passed=len(calls) >= 10 and match >= 9)


def main(argv=None):
    args = parser("P2 R0 identity").parse_args(argv)
    stats = execute("P2 R0 identity", jobs(), args)
    if stats:
        print("P2 evaluation:", evaluate(stats["run_path"]), "(mock: not meaningful)" if not args.live else "")
    return stats


if __name__ == "__main__":
    main()
