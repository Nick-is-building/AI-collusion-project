"""Dry run: build the exact request kwargs of every replay call (correct and bait versions) with a mock model.

No network and no API call: `experiments.agents.completion` is replaced by the mock in
src/replay/request.py, and everything else is Shi et al.'s own verdict-phase code path.

Items: the 173 candidates of the plan-text ("exact") frame (a superset of the committed 168) with
variants R0, CUT (= R0'), R2, R3, R4, R4n on the correct version; the 63-case fidelity set with R0.
Bait versions: every saved bait (data/derived/baits/*.json) with R1 (= CUT with the bait), R2, R3,
R4, R4n.

Output: data/derived/dryrun_request_hashes.csv (item, variant, request hash, message-list hash,
number of messages, characters). Usage: .venv/bin/python -m src.replay.dry_run
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.replay.item_tables import item_id
from src.replay.request import canonical_json, messages_hash, mock_backend, request_hash, run_verdict
from src.replay.variants import build, load_item

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "dryrun_request_hashes.csv"
FRAME = ROOT / "data" / "derived" / "verdict_frame_flash_lite_unconstrained_exact_rule.csv"
FIDELITY = ROOT / "data" / "derived" / "items" / "fidelity_set.csv"
CORRECT_VARIANTS = ("R0", "CUT", "R2", "R3", "R4", "R4n")


def rows():
    f = pd.read_csv(FRAME)
    cand = f[f.peer_correct & f.task_type.isin(["record_extraction", "data_search"])]
    jobs = [(r.trace, r.ep_index, "alice", r.task_type, v, "candidate") for r in cand.itertuples()
            for v in CORRECT_VARIANTS]
    fid = pd.read_csv(FIDELITY)
    jobs += [(r.trace, r.ep_index, r.judge, r.task_type, "R0", "fidelity") for r in fid.itertuples()]
    baits = {}
    for p in sorted((ROOT / "data" / "derived" / "baits").glob("*.json")):
        rec = json.loads(p.read_text())
        baits[(rec["trace"], rec["ep_index"])] = rec["bob_r1_content"]
        jobs += [(rec["trace"], rec["ep_index"], "alice", rec["task_type"], v, "bait")
                 for v in ("CUT", "R2", "R3", "R4", "R4n")]
    backend = mock_backend("accept")
    for trace, ep, judge, task_type, variant, source in jobs:
        ctx = load_item(trace, ep, judge)
        bait = baits[(trace, ep)] if source == "bait" else None
        msgs = build(ctx, variant, bob_r1_content=bait)
        res = run_verdict(msgs, task_type, backend, judge=judge)
        assert len(res.requests) == 1 and canonical_json(res.requests[0]["messages"]) == canonical_json(msgs)
        yield dict(item_id=item_id(trace, ep, judge), source=source,
                   variant=("R1" if (bait and variant == "CUT") else variant), version="bait" if bait else "correct",
                   task_type=task_type, n_messages=len(msgs), chars=len(canonical_json(msgs)),
                   messages_sha256=messages_hash(msgs), request_sha256=request_hash(res.requests[0]))


def main():
    d = pd.DataFrame(rows())
    d.to_csv(OUT, index=False)
    print(f"{len(d)} dry-run requests; written {OUT}")
    print(d.groupby(["source", "variant"]).size().to_dict())
    print("duplicate request hashes within a variant:", int(d.duplicated(["variant", "request_sha256"]).sum()))


if __name__ == "__main__":
    main()
