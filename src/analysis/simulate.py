"""Simulated verdict data for testing the analysis (CLEARLY SYNTHETIC; never mixed with observed data).

calls are generated for the real main-list structure (items nested in trajectories) with
P(REJECT) = logistic(base[variant, version] + u_cluster + v_item), u ~ N(0, sd_cluster),
v ~ N(0, sd_item): strong within-trajectory and within-item correlation. Every cell of the main-run
design is generated (two draws for the four primary cells), plus R6 gate outcomes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.runner.jobs import BAIT_CELLS, CORRECT_CELLS

NULL_BASE = {("R1", "bait"): -1.0, ("R2", "bait"): -1.0, ("R3", "bait"): -1.0, ("R4", "bait"): -1.0,
             ("R4n", "bait"): -1.0, ("R5", "bait"): -1.0, ("R6", "bait"): -1.0,
             ("R0", "correct"): -2.5, ("R0p", "correct"): -2.5, ("R2", "correct"): -2.5, ("R3", "correct"): -2.5,
             ("R4", "correct"): -2.5, ("R4n", "correct"): -2.5, ("R5", "correct"): -2.5, ("R6", "correct"): -2.5}


def logit(p):
    return np.log(p / (1 - p))


def simulate(meta: pd.DataFrame, base: dict | None = None, sd_cluster: float = 1.0, sd_item: float = 1.0,
             p_missing: float = 0.0, seed: int = 0) -> pd.DataFrame:
    base = dict(NULL_BASE if base is None else base)
    rng = np.random.default_rng(seed)
    clusters = meta.cluster.unique()
    u = dict(zip(clusters, rng.normal(0, sd_cluster, len(clusters))))
    rows = []
    for item, m in meta.iterrows():
        v = rng.normal(0, sd_item)
        for version, cells in (("bait", BAIT_CELLS), ("correct", CORRECT_CELLS)):
            for variant, draw in cells:
                p = 1 / (1 + np.exp(-(base[(variant, version)] + u[m.cluster] + v)))
                y = float(rng.random() < p)
                if rng.random() < p_missing:
                    y = np.nan
                row = dict(call_id=f"sim:{item}:{variant}:{version}:{draw}", item_id=item, variant=variant,
                           version=version, draw=draw, verdict_status="ok" if y == y else "missing_forced",
                           verdict=None if y != y else ("reject" if y else "accept"), reasoning="", y=y)
                if variant == "R6":
                    row.update(r6_first_y=y, r6_gate_fired=False, r6_retry_y=np.nan, r6_final_y=y,
                               r6_first_compliant=True, first_reasoning="")
                rows.append(row)
    return pd.DataFrame(rows)
