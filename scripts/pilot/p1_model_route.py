"""P1 model route (plan section 10): one verdict call to gemini/gemini-3.1-flash-lite and one
availability call to gemini/gemini-3.7-flash; response_model is logged by the runner.

Request: the R4 context (correct version) of the first pilot hold-out item by item_id (short
context, about 3-6k tokens; a real verdict request with the forced submit_verdict tool). The
3.7-Flash call has no documented price: it is refused unless --allow-37 is given, and is then
charged at the placeholder in configs/prices.yaml (fail closed). Pass: Flash-Lite answers with a
response_model; 3.7 availability is recorded either way (a missing call is a result, not a failure).

  .venv/bin/python -m scripts.pilot.p1_model_route [--plan] [--allow-37]
"""
from scripts.pilot.common import execute, holdout, make_job, parser


def jobs(allow_37=False):
    row = holdout().iloc[0]
    out = [make_job("P1", row, "R4")]
    if allow_37:
        out.append(make_job("P1-37", row, "R4", model="gemini/gemini-3.7-flash", allow_undocumented_price=True))
    return out


def main(argv=None):
    ap = parser("P1 model route")
    ap.add_argument("--allow-37", action="store_true", help="include the unpriced 3.7-Flash availability call")
    args = ap.parse_args(argv)
    note = None if args.allow_37 else "P1: gemini/gemini-3.7-flash availability call (1 call) excluded: no documented price; add --allow-37"
    return execute("P1 model route", jobs(args.allow_37), args, extra_note=note)


if __name__ == "__main__":
    main()
