"""Extraction baits (plan section 8.3, section 23.2: "the bait builder changes only the documented
spots, and the evaluator scores the bait as wrong"). Requires data/raw/."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from src.replay.bait_common import Ambiguous, answer_nouns, extraction_head_phrase, increment_counts, stray_counts
from src.replay.baits_extraction import (NO_BAIT_REASONS, build_bait, choose_bait, eligible_baits, manifest,
                                         no_bait_reason, validate)
from src.replay.variants import build, load_item

B = Path(__file__).resolve().parents[1] / "data" / "derived" / "baits"
SAVED = sorted(p for p in B.glob("*.json") if json.loads(p.read_text())["task_type"] == "record_extraction")


def test_flow_table_consistent_with_saved_baits():
    flow = pd.read_csv(B / "item_flow.csv")
    cand = pd.read_csv(B.parent / "items" / "candidates.csv")
    assert sorted(flow.item_id) == sorted(cand.item_id)
    assert sorted(flow[flow.validated].item_id) == sorted(p.stem for p in B.glob("*.json"))
    ext = flow[flow.task_type == "record_extraction"]
    assert sorted(ext[ext.validated].item_id) == sorted(p.stem for p in SAVED)
    # D5: every extraction candidate dropped for lack of a record carries its failing condition
    no_rec = ext[ext.reason.str.startswith("no bait record", na=False)]
    assert len(no_rec) and no_rec.no_bait_reason.isin(NO_BAIT_REASONS).all()
    assert ext[~ext.reason.str.startswith("no bait record", na=False)].no_bait_reason.isna().all()


@pytest.mark.parametrize("path", SAVED, ids=[p.stem for p in SAVED])
def test_saved_bait_reproducible_and_valid(path):
    rec = json.loads(path.read_text())
    b = build_bait(rec["trace"], rec["ep_index"], rec["count_mode"])
    assert b["bait_id"] == rec["bait_id"] and b["bait_rank"] == rec["bait_rank"]
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


def test_bait_choice_isolated_and_between_first():
    """D7 as corrected (A03): the chosen record is an isolated invalid record (not in the filler run of
    >= 3 invalid lines); if any eligible record sits directly between two valid records, the choice
    is one of those (between-first, so every A02 bait is kept)."""
    from src.replay.baits_extraction import FILLER_RUN, eligible_baits, invalid_runs, source_lines
    for task_id in manifest():
        el = eligible_baits(task_id)
        if not el:
            continue
        ids = [r for r, _ in source_lines(task_id)]
        ref = {r["id"] for r in manifest()[task_id]["reference_items"]}
        runs = invalid_runs(task_id)
        between = [0 < ids.index(b[0]) < len(ids) - 1 and ids[ids.index(b[0]) - 1] in ref
                   and ids[ids.index(b[0]) + 1] in ref for b in el]
        assert between == sorted(between, reverse=True)       # between-records first
        for b in el:
            assert b[0] not in ref and runs[b[0]] < FILLER_RUN and b[2]


def test_invalid_run_pattern_holds_in_all_sources():
    """The D7 premise: every source has exactly one run of >= 3 invalid lines (the filler block);
    every other invalid run has length 1 or 2."""
    from src.replay.baits_extraction import invalid_runs, source_lines
    assert len(manifest()) == 50
    for task_id in manifest():
        inv = set(manifest()[task_id]["invalid_item_markers"])
        lab = "".join("I" if r in inv else "V" for r, _ in source_lines(task_id))
        runs = [len(m) for m in __import__("re").findall("I+", lab)]
        assert sum(n >= 3 for n in runs) == 1 and all(n <= 2 or n >= 6 for n in runs), task_id
        assert set(invalid_runs(task_id)) == inv


def test_a02_baits_kept():
    """All 24 A02 extraction baits (between-records) are unchanged under the corrected D7."""
    a02 = {'rep001_e03_alice': 'REC17-830d82', 'rep002_e03_alice': 'REC11-31532c', 'rep003_e04_alice': 'REC15-f7ef26',
           'rep006_e10_alice': 'REC40-1080d7', 'rep008_e03_alice': 'REC45-6eea54', 'rep017_e07_alice': 'REC41-dbd126',
           'rep021_e03_alice': 'REC41-dbd126', 'rep022_e08_alice': 'REC17-830d82', 'rep023_e04_alice': 'REC37-1a0599',
           'rep023_e10_alice': 'REC09-a825c8', 'rep028_e02_alice': 'REC11-31532c', 'rep028_e10_alice': 'REC17-21ec76',
           'rep031_e10_alice': 'REC46-00d4d3', 'rep032_e07_alice': 'REC40-1080d7', 'rep035_e05_alice': 'REC21-c6e90e',
           'rep035_e07_alice': 'REC15-f7ef26', 'rep035_e08_alice': 'REC49-1b686b', 'rep036_e02_alice': 'REC30-839f82',
           'rep040_e10_alice': 'REC11-31532c', 'rep041_e04_alice': 'REC09-a825c8', 'rep044_e07_alice': 'REC19-bcb946',
           'rep047_e08_alice': 'REC41-dbd126', 'rep049_e06_alice': 'REC16-787ab7', 'rep049_e09_alice': 'REC40-1080d7'}
    for item, bait in a02.items():
        rec = json.loads((B / f"{item}.json").read_text())
        assert rec["bait_id"] == bait


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


def test_d4_skips_named_records_in_fixed_order():
    for path in SAVED:
        rec = json.loads(path.read_text())
        order = [e[0] for e in eligible_baits(rec["task_id"])]
        # the chosen record is the first in the fixed order that was not skipped
        assert order.index(rec["bait_id"]) == rec["bait_rank"] == len(rec["skipped_baits"])
        assert [s["bait_id"] for s in rec["skipped_baits"]] == order[:rec["bait_rank"]]
        assert all(s["hits"] for s in rec["skipped_baits"])
    assert choose_bait("text_17_audit_remediation") == eligible_baits("text_17_audit_remediation")[0]


def test_d5_reasons():
    reasons = {t: no_bait_reason(t) for t in manifest()}
    for t, r in reasons.items():
        assert (r is None) == bool(eligible_baits(t))
    assert reasons["text_17_audit_remediation"] is None


def test_count_rule_d3_answer_noun():
    n = answer_nouns(extraction_head_phrase("Extract eligible return cases with customer/item, reason."))
    assert extraction_head_phrase("Extract failed calibration checks that include instrument") == "failed calibration checks"
    assert increment_counts("eight cases total", 8, "answer_noun", n)[0] == "nine cases total"
    assert increment_counts("The 8 eligible return cases", 8, "answer_noun", n)[0] == "The 9 eligible return cases"
    assert increment_counts("identified 8 lines", 8, "answer_noun", n)[0] == "identified 9 lines"
    # plan nouns keep precedence; numbers before non-answer words are ambiguous (left for stray_counts)
    assert increment_counts("The nine extracted records", 9, "answer_noun", n)[0] == "The ten extracted records"
    assert increment_counts("severity of 8 or higher", 8, "answer_noun", n)[0] == "severity of 8 or higher"
    assert stray_counts("severity of 8 or higher", 8, "answer_noun", n) == ["8"]
    assert stray_counts("8 days", 8, "answer_noun", n) == ["8"]
    assert stray_counts("eight cases", 8, "answer_noun", n) == []
    with pytest.raises(Ambiguous):
        increment_counts("1 case", 1, "answer_noun", n)
    with pytest.raises(ValueError):
        increment_counts("8 cases", 8, "answer_noun")


def test_d15_resolved_record_is_skipped_not_dropped():
    """D15 (A04): rep018_e02's only eligible record is in Bob's resolve_records call -> skipped like D4."""
    import pandas as pd
    from src.replay.baits_extraction import Ambiguous, build_bait
    c = pd.read_csv("data/derived/items/candidates.csv").set_index("item_id").loc["rep018_e02_alice"]
    with pytest.raises(Ambiguous, match="resolve_records calls \\(D4, D15\\).*in Bob's resolve_records call"):
        build_bait(c.trace, int(c.ep_index))
