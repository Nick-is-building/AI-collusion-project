"""P10 cost (plan section 10): measured cost per call from logged usage, and a projection of the
total cost (pass: projected total below the 250 USD hard cap).

Measured: the ledger over results/raw/*.jsonl (live) or logs/mock_runs/raw (mock), per check:
calls, cost, mean cost per call, mean input/output tokens.
Projection (plan section 12 call counts; makes no call): token estimates from
src/runner/estimates.py (R0 = original input tokens; other variants scaled by request characters;
output = p95 of original verdict calls), Flash-Lite prices without cache savings:
  core: per main item (min(n_main, 148)) bait R1 R2 R3 R4 R4n R5 R6 + correct R0 R0' R2 R3 R4 R4n R5 R6
        + second draws of R1(bait), R0', R4(bait), R4(correct)            = 19 calls per item
  natural-error set: N1 (cut) and N4 (R4) per item
  fidelity set: R0 x 3 samples per case
  Haiku: R1(bait), R0', R4(bait), R4(correct) per main item at Haiku prices (Gemini token counts)
  R1-live: 40 items x 10 calls (rounds 2-5 both agents + 2 verdicts) at 1.1 x cut tokens (rough)
  3.7 Flash: not projected (no documented price)

  .venv/bin/python -m scripts.pilot.p10_cost [--live]
"""
import pandas as pd

from scripts.pilot.common import DIRS, ROOT, candidates, fidelity, parser
from src.runner.costs import PriceTable, iter_call_lines, load_yaml
from src.runner.estimates import input_tokens, projected_call_cost

FL = "gemini/gemini-3.1-flash-lite"
HAIKU = "anthropic/claude-haiku-5-5"
CORE = ["R1", "R2", "R3", "R4", "R4n", "R5", "R6"] + ["R0", "R0p", "R2", "R3", "R4", "R4n", "R5", "R6"] + \
       ["R1", "R0p", "R4", "R4"]


def measured(results_dir):
    rows = [dict(check=r["check"], cost=r["cost_usd"] or 0.0,
                 inp=sum(u.get("input_tokens") or 0 for u in r["usage"]),
                 out=sum(u.get("billable_output_tokens") or u.get("provider_output_tokens") or 0 for u in r["usage"]))
            for r in iter_call_lines(results_dir)]
    if not rows:
        return None
    d = pd.DataFrame(rows)
    return d.groupby("check").agg(calls=("cost", "size"), cost_usd=("cost", "sum"), mean_cost=("cost", "mean"),
                                  mean_in=("inp", "mean"), mean_out=("out", "mean"))


def projection(prices=None):
    prices = prices or PriceTable()
    c = candidates()
    main = c[c.set == "main"].sort_values("item_id")
    n_main = min(len(main), 148)
    main = main.head(n_main)  # cost projection only; which items survive is decided by bait validation
    comp = {}
    comp["core (Flash-Lite)"] = (len(main) * len(CORE), sum(
        projected_call_cost(prices, FL, input_tokens(i, v)) for i in main.item_id for v in CORE))
    nat = pd.read_csv(ROOT / "data" / "derived" / "items" / "natural_error_set.csv")
    comp["natural-error N1, N4"] = (2 * len(nat), sum(
        projected_call_cost(prices, FL, input_tokens(i, v)) for i in nat.item_id for v in ("CUT", "R4")))
    fid = fidelity().drop_duplicates("item_id")
    comp["fidelity R0 x3"] = (3 * len(fid), 3 * sum(projected_call_cost(prices, FL, input_tokens(i, "R0"))
                                                    for i in fid.item_id))
    comp["Haiku R1/R0'/R4 both"] = (4 * len(main), sum(
        projected_call_cost(prices, HAIKU, input_tokens(i, v)) for i in main.item_id
        for v in ("R1", "R0p", "R4", "R4")))
    live = main.item_id.tolist()[:40]
    comp["R1-live (rough)"] = (10 * len(live), sum(
        10 * projected_call_cost(prices, FL, int(1.1 * input_tokens(i, "CUT"))) for i in live))
    return n_main, comp


def main(argv=None):
    args = parser("P10 cost").parse_args(argv)
    mode = "live" if args.live else "mock"
    rdir = args.results_dir or DIRS[mode][0]
    m = measured(rdir)
    print(f"P10 measured ({mode}, {rdir}):")
    print(m.to_string() if m is not None else "  no logged calls")
    if mode == "mock":
        print("  (mock: costs use stand-in token counts, not real spend)")
    n_main, comp = projection()
    print(f"P10 projection for the main runs (n_main = {n_main}; no call made):")
    total = 0.0
    for k, (n, usd) in comp.items():
        total += usd
        print(f"  {k:28s} {n:6d} calls  {usd:8.2f} USD")
    cap = load_yaml("caps.yaml")["hard_cap_usd"]
    print(f"  {'total':28s} {sum(n for n, _ in comp.values()):6d} calls  {total:8.2f} USD  "
          f"(hard cap {cap}; below cap: {total < cap})")
    return dict(total=total, components=comp, n_main=n_main)


if __name__ == "__main__":
    main()
