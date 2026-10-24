"""A03 task 1: does the R0 token mismatch equal -5 x (unmatched resolve_records items in the kept
history)? Offline; uses the logged API input_tokens of the live P2/P9 R0 calls."""
import json

from scripts.a03.r0_bisection import api_reported, logged, parse
from src.replay.variants import build, load_item


def nulls(msgs):
    n_tool = n_all = 0
    for m in msgs:
        if m["role"] == "tool" and m.get("name") == "resolve_records":
            try:
                n_tool += sum(1 for it in json.loads(m["content"]).get("items", []) if it.get("record_id") is None)
            except (ValueError, AttributeError):
                pass
        n_all += json.dumps(m).count('record_id\\": null') + json.dumps(m).count('record_id\\\\\\":null')
    return n_tool, n_all


def main():
    rows = []
    for item, toks in sorted(api_reported().items()):
        tr, k, j = parse(item)
        n_tool, n_all = nulls(build(load_item(tr, k, j), "R0"))
        api = sorted(toks)[0]
        diff = api - logged(tr, k, j)
        rows.append((item, diff, n_tool, diff == -5 * n_tool))
        print(f"{item:20s} diff {diff:5d}  unmatched_items {n_tool:3d}  predicted {-5 * n_tool:5d}  "
              f"{'OK' if diff == -5 * n_tool else 'NO'}")
    ok = sum(r[3] for r in rows)
    print(f"prediction exact in {ok}/{len(rows)} items; mismatched items {sum(r[1] != 0 for r in rows)}")


if __name__ == "__main__":
    main()
