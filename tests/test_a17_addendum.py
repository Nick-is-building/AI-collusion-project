"""A17 analysis (D41) on SYNTHETIC calls frames (labelled synthetic; no real outcome is used)."""
import json

import pandas as pd

from scripts.analysis import a17_addendum as A
from scripts.analysis.a06_addendum import cluster_meta
from scripts.analysis.a13_addendum import items_info


def _frame(rule):
    """rule(item_index, variant, version) -> REJECT probability 0/1 (synthetic)."""
    items = sorted(o["item_id"] for o in A.a17_items())
    rows = []
    for i, it in enumerate(items):
        for v, ver in A.CELLS:
            for d in (1, 2):
                y = float(rule(i, v, ver))
                rows.append(dict(call_id=f"syn:{it}:{v}:{ver}:{d}", item_id=it, variant=v, version=ver, draw=d,
                                 y=y, verdict="reject" if y else "accept", reasoning="synthetic", check="HAIKU"))
    return pd.DataFrame(rows), items


def test_block_family_rows_comparisons():
    hk, items = _frame(lambda i, v, ver: ver == "omission" and (v == "R4" or (v == "R1+CHK" and i % 2 == 0)))
    fl, _ = _frame(lambda i, v, ver: ver == "omission" and v in ("R4", "R2"))
    meta, info = cluster_meta(), items_info()
    prim = [i for i in items if i not in A.EXPECTED_PRIMARY_EXCLUSIONS]
    b = A.block(hk, fl, None, meta, info, prim)
    p = b["primary"]
    assert b["n_items"] == 48
    assert p["G"]["estimate"] == 1.0 and p["G"]["significant"] and p["D_G"]["tested"]
    assert p["H"]["estimate"] == 0.0 and not p["H"]["significant"] and p["D_H"]["tested"] is False
    assert abs(p["C"]["estimate"] - 0.5) < 0.05 and p["C"]["p_holm"] >= p["C"]["p"]
    rows = b["interpretation"]["rows"]
    assert rows["row1_G_significant_positive"] and not rows["row4_H_significant_positive"]
    cmp_ = b["haiku_minus_flash_lite"]
    assert cmp_["cells"]["R2|omission"]["difference"]["estimate"] == -1.0
    assert cmp_["contrasts"]["H"]["difference"]["estimate"] == -1.0
    assert b["haiku_minus_flash_38"] == {"status": "A16 not finished"}
    assert "R1|bait" in b["secondary"]["per_cell"] and b["secondary"]["per_cell"]["R1|bait"]["calls"] == 0
    b2 = A.block(hk, fl, fl, meta, info, items)
    assert b2["n_items"] == 50 and b2["haiku_minus_flash_38"]["contrasts"]["G"]["difference"]["estimate"] == 0.0
    json.dumps(b, default=str)


def test_exclusions_match_a16_frozen_file():
    from scripts.analysis import a16_addendum
    assert sorted(a16_addendum.load_exclusions()["excluded"]) == A.EXPECTED_PRIMARY_EXCLUSIONS
