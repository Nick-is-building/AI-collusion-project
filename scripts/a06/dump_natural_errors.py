"""Reading aid for the D24 rubric (A06 task 1): for every natural-error item, write what Alice sees
for the decision (Bob's Task information + Bob's round-1 message with the pretty-printed raw log)
plus the evaluator's details (not visible to Alice) to scratch/a06/natural/<item_id>.txt.
No outcome of any run is read."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.replay.bait_common import pretty_log
from src.replay.traces import get_log_raw, episode_bounds, load_trace
from src.replay.variants import load_item

OUT = Path("scratch/a06/natural")


def task_information(ctx) -> str:
    opening = ctx.messages[ctx.comm_opening_idx(ctx.ep_index)]["content"]
    m = re.search(r"### Bob's Task information\n(.*?)(?=\n### |\Z)", opening, re.S)
    return m.group(1) if m else "(no Bob's Task information section)\n" + opening


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    nat = pd.read_csv("data/derived/items/natural_error_set.csv")
    for r in nat.itertuples():
        t = load_trace(r.trace)
        ctx = load_item(r.trace, int(r.ep_index))
        bob = t["results"][int(r.ep_index)]["agents"]["bob"]
        bob_msg = ctx.messages[ctx.cut_idx]["content"]
        raw = get_log_raw(bob["messages"], *episode_bounds(t, int(r.ep_index), "bob"))
        framing = bob_msg.replace(raw, "<<RAW LOG>>") if raw and raw in bob_msg else bob_msg
        ev = {k: bob.get(k) for k in ("extraction_eval", "data_search_eval", "code_analysis_eval") if bob.get(k)}
        evx = {k: v for k, v in bob.items() if k.endswith("eval") or k in ("quality_verdict", "true_expected_verdict")}
        txt = [f"# {r.item_id}  {r.task_type}  {r.peer_task_id}  error_type={r.error_type}",
               "\n## Bob's Task information (visible to Alice)\n", task_information(ctx),
               "\n## Bob's round-1 framing (raw log replaced by <<RAW LOG>>)\n", framing,
               "\n## Raw log, pretty\n", pretty_log(raw) if raw else "(none)",
               "\n## Evaluator (NOT visible to Alice)\n", json.dumps(evx, indent=1, default=str)[:20000]]
        (OUT / f"{r.item_id}.txt").write_text("\n".join(txt))
    print(len(nat), "items written to", OUT)


if __name__ == "__main__":
    main()
