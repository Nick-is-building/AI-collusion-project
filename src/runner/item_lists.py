"""Item lists for the pilot and the main run (PROJECT_PLAN.md sections 8.1, 8.4, 10; A03).

All lists are derived from committed tables; every random draw uses its own
numpy.random.default_rng(SEED) instance, so the lists do not depend on each other or on call order.

  main_items()         validated baits in the main list (data/derived/baits/item_flow.csv, set "main",
                       validated) joined with candidates.csv; sorted by item_id. D8: used as is
                       (109 items); the plan's cap of 148 is not reached, so no random drop.
  holdout_items()      validated baits in the pilot hold-out (P11), sorted by item_id.
  p5_items()           5 hold-out items with a validated bait for P5 (technical pilot of R4, R4n, R5, R6):
                       largest-remainder allocation of 5 over the task types of the validated hold-out
                       baits; per task type (sorted) rng.choice without replacement from item_ids sorted.
                       Hold-out items are used so that no main item is touched by a pilot.
  r1live_subset()      40 main items for R1-live (plan 8.4): rng.choice(sorted main item_ids, 40,
                       replace=False), returned sorted.
  natural_error_items()  the 35 natural-error items (N1, N4), from natural_error_set.csv.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "derived" / "items"
BAITS = ROOT / "data" / "derived" / "baits"
SEED = 2026
N_P5 = 5
N_R1LIVE = 40


def _validated(set_name: str) -> pd.DataFrame:
    flow = pd.read_csv(BAITS / "item_flow.csv")
    ok = flow[(flow.set == set_name) & flow.validated.astype(bool)][["item_id"]]
    c = pd.read_csv(ITEMS / "candidates.csv")
    return c.merge(ok, on="item_id").sort_values("item_id").reset_index(drop=True)


def main_items() -> pd.DataFrame:
    return _validated("main")


def holdout_items() -> pd.DataFrame:
    return _validated("pilot_holdout")


def _allocate(counts: dict, n: int) -> dict:
    total = sum(counts.values())
    quota = {t: n * c / total for t, c in counts.items()}
    alloc = {t: int(q) for t, q in quota.items()}
    for t in sorted(quota, key=lambda t: (-(quota[t] - alloc[t]), t))[:n - sum(alloc.values())]:
        alloc[t] += 1
    return alloc


def p5_items() -> pd.DataFrame:
    h = holdout_items()
    rng = np.random.default_rng(SEED)
    alloc = _allocate(h.task_type.value_counts().to_dict(), N_P5)
    ids = []
    for t in sorted(alloc):
        pool = sorted(h[h.task_type == t].item_id)
        ids += list(rng.choice(pool, size=alloc[t], replace=False))
    return h[h.item_id.isin(ids)].sort_values("item_id").reset_index(drop=True)


def r1live_subset() -> list[str]:
    ids = sorted(main_items().item_id)
    rng = np.random.default_rng(SEED)
    return sorted(rng.choice(ids, size=min(N_R1LIVE, len(ids)), replace=False).tolist())


def natural_error_items() -> pd.DataFrame:
    return pd.read_csv(ITEMS / "natural_error_set.csv").sort_values("item_id").reset_index(drop=True)


def load_bait(item_id: str) -> dict:
    return json.loads((BAITS / f"{item_id}.json").read_text())


def load_bait_content(item_id: str) -> str:
    return load_bait(item_id)["bob_r1_content"]
