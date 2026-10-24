"""Committed item tables have the sizes and structure fixed by the plan (sections 8.1, 8.4, 8.7)."""
import json
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parents[1] / "data" / "derived" / "items"


def test_candidates():
    c = pd.read_csv(D / "candidates.csv")
    assert len(c) == 168 and c.item_id.is_unique
    assert c.groupby(["set", "task_type"]).size().to_dict() == {
        ("main", "data_search"): 87, ("main", "record_extraction"): 61,
        ("pilot_holdout", "data_search"): 12, ("pilot_holdout", "record_extraction"): 8}
    assert c.peer_correct.all() and (c.evaluation_episode >= 2).all()
    m = json.loads(c.correct_counterpart.iloc[0])
    assert m["R1"] == "R0p" and all(m[k] == k for k in ("R2", "R3", "R4", "R4n", "R5", "R6"))


def test_natural_error_set():
    n = pd.read_csv(D / "natural_error_set.csv")
    assert len(n) == 35 and not n.peer_correct.any()
    assert n.error_type.value_counts().to_dict() == {
        "omission": 19, "data_search": 6, "both": 4, "commission": 3, "code_analysis": 3}


def test_fidelity_set():
    f = pd.read_csv(D / "fidelity_set.csv")
    rej = f[f.role == "original_reject"]
    acc = f[f.role == "matched_accept"]
    assert len(rej) == 21 and (rej.verdict == "reject").all()
    assert len(acc) == 42 and acc.item_id.is_unique and (acc.verdict == "accept").all()
    assert acc.matched_to.value_counts().eq(2).all()
    m = acc.merge(rej[["item_id", "task_type", "evaluation_episode"]], left_on="matched_to", right_on="item_id",
                  suffixes=("", "_r"))
    assert (m.task_type == m.task_type_r).all() and (m.evaluation_episode == m.evaluation_episode_r).all()
