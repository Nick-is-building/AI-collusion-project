"""A06 task 2: natural-error by decidability (synthetic calls, labelled as such)."""
import numpy as np
import pandas as pd

from scripts.analysis.verify_all import natural_by_decidability


def test_natural_by_decidability_synthetic():
    cl = pd.read_csv("data/derived/rubric/natural_error_decidability.csv")
    rows = []
    for i, iid in enumerate(cl.item_id):            # SYNTHETIC verdicts: N1 rejects every 2nd item, N4 none
        rows.append(dict(item_id=iid, variant="N1", version="correct", draw=1, y=float(i % 2 == 0)))
        rows.append(dict(item_id=iid, variant="N4", version="correct", draw=1, y=0.0))
    r = natural_by_decidability(pd.DataFrame(rows))
    assert r["overall"]["items"] == 35 and r["overall"]["N1_rejects"] == 18 and r["overall"]["N4_rejects"] == 0
    assert sum(v["items"] for v in r["by_decidability"].values()) == 35
    exp = np.mean([i % 2 == 0 for i, d in enumerate(cl.decidable) if d == "yes"])
    assert abs(r["by_decidability"]["yes"]["detection_N1"] - exp) < 1e-12
