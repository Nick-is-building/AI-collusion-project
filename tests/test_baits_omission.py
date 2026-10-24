"""D25 omission baits (A06): builder, validation, determinism."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.replay.bait_common import Ambiguous
from src.replay.baits_omission import (OUT, build_omission, candidate_orders, decrement_counts, validate)
from src.replay.traces import load_trace
from src.replay.variants import build, load_item

SAVED = sorted(OUT.glob("rep*_alice.json"))


def test_decrement_counts_d3_rule():
    nouns = frozenset({"record", "records", "item", "check", "checks"})
    t, ch = decrement_counts("I found nine records and 9 failed checks.", 9, nouns)
    assert t == "I found eight records and 8 failed checks." and len(ch) == 2
    with pytest.raises(Ambiguous):
        decrement_counts("There are 3 records.", 9, nouns)
    with pytest.raises(Ambiguous):
        decrement_counts("two records", 2, nouns)


def test_scope_and_flow():
    flow = pd.read_csv(OUT / "item_flow.csv")
    cand = pd.read_csv("data/derived/items/candidates.csv")
    main_ex = cand[(cand.set == "main") & (cand.task_type == "record_extraction")]
    assert sorted(flow.item_id) == sorted(main_ex.item_id) and len(flow) == 64
    assert flow.validated.sum() == len(SAVED) == 50
    assert not set(flow.item_id) & set(cand[cand.set == "pilot_holdout"].item_id)


def test_orders_are_deterministic_permutations():
    a, b = candidate_orders(), candidate_orders()
    assert a == b
    flow = pd.read_csv(OUT / "item_flow.csv").set_index("item_id")
    for iid, order in a.items():
        assert flow.loc[iid, "order"].split() == order


@pytest.mark.parametrize("p", SAVED[:50], ids=lambda p: p.stem)
def test_saved_omission_rebuilds_and_validates(p):
    s = json.loads(p.read_text())
    b = build_omission(s["trace"], s["ep_index"], s["order"])
    assert b["bob_r1_content"] == s["bob_r1_content"] and b["removed_id"] == s["removed_id"]
    v = validate(b)
    assert all(v.values()), v
    ev = b["evaluator"]
    assert ev["missing_references"] == [s["removed_id"]] and ev["extra_references"] == []
    # the removed record is the first in the seeded order that is not named (skips listed)
    assert s["order"].index(s["removed_id"]) == s["removed_rank"] == len(s["skipped_records"])
    # Alice's R1 / R4 context differs from the original only in Bob's round-1 message
    ctx = load_item(s["trace"], s["ep_index"])
    for v_ in ("CUT", "R4"):
        o, n = build(ctx, v_), build(ctx, v_, bob_r1_content=s["bob_r1_content"])
        assert sum(a != b for a, b in zip(o, n)) == 1 and len(o) == len(n)
