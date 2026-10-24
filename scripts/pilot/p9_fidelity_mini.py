"""P9 fidelity mini (plan section 10; diagnostic only): 8 original REJECTs and 12 ACCEPTs, R0, two
samples each = 40 calls.

rng = default_rng(2026): 8 REJECT item_ids drawn without replacement from fidelity_set.csv
(role original_reject, sorted by item_id); then 12 of the matched ACCEPTs of those 8 (16, sorted
by item_id), drawn without replacement with the same generator. The judge is the original judge
(Alice or Bob). Overlap with main items is possible (R0 on the correct version, diagnostic).

  .venv/bin/python -m scripts.pilot.p9_fidelity_mini [--plan]
"""
from scripts.pilot.common import execute, fidelity, make_job, parser, read_calls, rng


def items():
    f = fidelity()
    g = rng()
    rej = f[f.role == "original_reject"].sort_values("item_id")
    pick_r = list(g.choice(rej.item_id.tolist(), size=8, replace=False))
    acc = f[(f.role == "matched_accept") & f.matched_to.isin(pick_r)].sort_values("item_id")
    pick_a = list(g.choice(acc.item_id.tolist(), size=12, replace=False))
    return f[f.item_id.isin(pick_r + pick_a) & ~f.duplicated("item_id")].sort_values(["role", "item_id"])


def jobs():
    return [make_job("P9", r, "R0", draw=d, judge=r.judge) for r in items().itertuples() for d in (1, 2)]


def evaluate(path):
    f = fidelity().drop_duplicates("item_id").set_index("item_id")
    calls = [c for c in read_calls(path) if c["check"] == "P9" and c["verdict_status"] == "ok"]
    out = {}
    for role in ("original_reject", "matched_accept"):
        cs = [c for c in calls if f.loc[c["item_id"], "role"] == role]
        out[role] = dict(n=len(cs), reject_rate=(sum(c["verdict"] == "reject" for c in cs) / len(cs)) if cs else None)
    return out


def main(argv=None):
    args = parser("P9 fidelity mini").parse_args(argv)
    stats = execute("P9 fidelity mini", jobs(), args)
    if stats:
        print("P9 evaluation (diagnostic):", evaluate(stats["run_path"]))
    return stats


if __name__ == "__main__":
    main()
