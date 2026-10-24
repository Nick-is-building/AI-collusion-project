"""A06 task 1 (D24): decidability classification and lexical-overlap measure."""
import json
from pathlib import Path

import pandas as pd

from src.analysis.lexical_overlap import exclusion_words, overlap, table

ROOT = Path(__file__).resolve().parents[1]


def test_classification_covers_natural_error_set_exactly():
    nat = pd.read_csv(ROOT / "data/derived/items/natural_error_set.csv")
    cl = pd.read_csv(ROOT / "data/derived/rubric/natural_error_decidability.csv")
    assert sorted(cl.item_id) == sorted(nat.item_id) and len(cl) == 35
    m = cl.merge(nat[["item_id", "task_type", "error_type"]], on="item_id", suffixes=("", "_nat"))
    assert (m.task_type == m.task_type_nat).all() and (m.error_type == m.error_type_nat).all()
    assert set(cl.decidable) <= {"yes", "no", "ambiguous"}
    assert cl.reason.str.len().min() > 20


def test_overlap_rule_on_plan_example():
    # PROJECT_PLAN.md 8.3 example (text_17): "Exclude observations marked informational or already closed"
    e = exclusion_words("Extract audit findings with owner. Exclude observations marked informational or already closed.")
    assert {"alrea", "close", "infor"} <= e
    from src.replay.baits_extraction import _words
    assert _words("Password rotation screenshots were missing last quarter, but the issue is already closed.") & e \
        == {"alrea", "close"}


def test_overlap_matches_bait_builder_overlap_words():
    for p in sorted((ROOT / "data/derived/baits").glob("rep*_alice.json")):
        b = json.loads(p.read_text())
        if b["task_type"] == "record_extraction":
            o = overlap(b["task_id"], b["bait_sentence"])
            assert o["overlap_words"].split() == sorted(b["overlap_words"]), b["item_id"]


def test_table_reproduces_committed_csv():
    t = table()
    c = pd.read_csv(ROOT / "data/derived/rubric/lexical_overlap.csv")
    assert len(t) == len(c) == 185
    assert t.overlap_n.fillna(-1).tolist() == c.overlap_n.fillna(-1).tolist()
