"""Item metadata for the analysis: cluster (trajectory), task type, episode, D2 flag, right-reason
markers (from the committed bait files and item tables)."""
from __future__ import annotations

import pandas as pd

from src.runner.item_lists import load_bait, main_items, natural_error_items


def main_meta(items: pd.DataFrame | None = None) -> pd.DataFrame:
    items = main_items() if items is None else items
    rows = []
    for r in items.itertuples():
        b = load_bait(r.item_id)
        rows.append(dict(item_id=r.item_id, cluster=r.trace.split(".")[0], task_type=r.task_type,
                         episode=int(r.evaluation_episode), bob_states_condition=bool(b.get("bob_states_condition", False)),
                         condition_class=b.get("condition_class"), markers=_markers(b)))
    return pd.DataFrame(rows).set_index("item_id")


def _markers(b: dict) -> dict:
    m = dict(b.get("right_reason_markers") or {})
    if b["task_type"] == "data_search" and b.get("condition_kind") in ("in", "cmp") and b.get("condition_class") == "categorical":
        m["added_value"] = str(b.get("added_value"))   # the violating category value (D2 "violated threshold")
    return m


def natural_meta() -> pd.DataFrame:
    n = natural_error_items()
    n = n.assign(cluster=n.trace.str.split(".").str[0])
    return n.set_index("item_id")[["cluster", "task_type", "error_type"]]
