"""Extraction baits (plan section 8.3, section 23.2: "the bait builder changes only the documented
spots, and the evaluator scores the bait as wrong"). Requires data/raw/."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from src.replay.bait_common import Ambiguous, increment_counts, stray_counts
from src.replay.baits_extraction import build_bait, choose_bait, manifest, validate
from src.replay.variants import build, load_item

B = Path(__file__).resolve().parents[1] / "data" / "derived" / "baits"
SAVED = sorted(B.glob("*.json"))


def test_flow_table_consistent_with_saved_baits():
    flow = pd.read_csv(B / "item_flow.csv")
    cand = pd.read_csv(B.parent / "items" / "candidates.csv")
    assert sorted(flow.item_id) == sorted(cand.item_id)
    assert sorted(flow[flow.validated].item_id) == sorted(p.stem for p in SAVED)
    assert not flow[flow.task_type == "data_search"].built.any()


@pytest.mark.parametrize("path", SAVED, ids=[p.stem for p in SAVED])
def test_saved_bait_reproducible_and_valid(path):
    rec = json.loads(path.read_text())
    b = build_bait(rec["trace"], rec["ep_index"], rec["count_mode"])
    assert b["bob_r1_content"] == rec["bob_r1_content"] and b["new_raw_log"] == rec["bait_raw_log"]
    assert hashlib.sha256(b["bob_r1_content"].encode()).hexdigest() == rec["bob_r1_content_sha256"]
    v = validate(b, rec["trace"], rec["ep_index"])
    assert all(v.values()), v
    # rule 1 with Shi et al.'s evaluator: exactly the bait is extra, nothing missing
    assert b["evaluator"]["extra_references"] == [rec["bait_id"]] and not b["evaluator"]["missing_references"]
    assert rec["bait_id"] in manifest()[rec["task_id"]]["invalid_item_markers"]
    # the original answer scores as correct (sanity of the evaluator call)
    from experiments.evaluation import evaluate_extraction_artifact
    orig = [e for e in json.loads(b["original_raw_log"]) if e["tool"] == "save_final_answer"][-1]
    assert evaluate_extraction_artifact(manifest()[rec["task_id"]],
                                        {"extraction_artifact": {"answer": orig["arguments"]["answer"]}})[
        "quality_verdict"] == "pass"
    # the new log is valid JSON and is the only log in the message
    json.loads(b["new_raw_log"])
    assert b["original_raw_log"] not in b["bob_r1_content"]
    # in Alice's replay contexts only Bob's round-1 message changes
    ctx = load_item(rec["trace"], rec["ep_index"])
    for variant in ("CUT", "R2", "R3", "R4", "R4n"):
        a, c = build(ctx, variant), build(ctx, variant, bob_r1_content=rec["bob_r1_content"])
        assert sum(x != y for x, y in zip(a, c)) == 1 and len(a) == len(c)


def test_bait_choice_sits_between_valid_records():
    for task_id in manifest():
        ch = choose_bait(task_id)
        if ch is None:
            continue
        from src.replay.baits_extraction import source_lines
        ids = [r for r, _ in source_lines(task_id)]
        ref = {r["id"] for r in manifest()[task_id]["reference_items"]}
        i = ids.index(ch[0])
        assert ids[i - 1] in ref and ids[i + 1] in ref and ch[0] not in ref and ch[2]


def test_count_rule():
    assert increment_counts("The nine extracted records", 9)[0] == "The ten extracted records"
    assert increment_counts("one record", 1)[0] == "two records"
    assert increment_counts("I found 12 items.", 12)[0] == "I found 13 items."
    with pytest.raises(Ambiguous):
        increment_counts("the 3 excluded records", 9)
    assert stray_counts("identified 12 lines", 12) == ["12"]
    assert stray_counts("identified 12 lines", 12, "any_noun") == []
    assert stray_counts("8. Sam", 8, "any_noun") == ["8"]
    assert increment_counts("12 lab results and 12 lines", 12, "any_noun")[0] == "13 lab results and 13 lines"
