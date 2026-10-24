"""A06 addendum analysis on SYNTHETIC call frames (labelled as such); no real outcome is used."""
import pandas as pd

from scripts.a06.launch_addendum import omission_items
from scripts.analysis.a06_addendum import cluster_meta, d25, d26
from src.runner.item_lists import main_items, r1live_subset


def _rows(items, variant, version, ys, check, draws=(1, 2)):
    return [dict(call_id=f"x:{check}:{i}:{variant}:{version}:{d}", item_id=i, variant=variant, version=version,
                 draw=d, verdict_status="ok", verdict="reject" if y else "accept", reasoning="", y=float(y), check=check)
            for i, y in zip(items, ys) for d in draws]


def test_d25_synthetic():
    om = [o["item_id"] for o in omission_items()]
    main_ids = set(main_items().item_id)
    inm, outm = [i for i in om if i in main_ids], [i for i in om if i not in main_ids]
    # SYNTHETIC: R4 detects every omission, R1 detects the first 10 only; correct versions always accepted
    a06 = pd.DataFrame(_rows(om, "R4", "omission", [1] * len(om), "OMIT")
                       + _rows(om, "R1", "omission", [1] * 10 + [0] * (len(om) - 10), "OMIT")
                       + _rows(outm, "R0p", "correct", [0] * len(outm), "OMIT")
                       + _rows(outm, "R4", "correct", [0] * len(outm), "OMIT"))
    main = pd.DataFrame(_rows(inm, "R0p", "correct", [0] * len(inm), "MAIN")
                        + _rows(inm, "R4", "correct", [0] * len(inm), "MAIN")
                        + _rows(inm, "R1", "bait", [1] * len(inm), "MAIN")
                        + _rows(inm, "R4", "bait", [1] * len(inm), "MAIN")).drop(columns="check")
    r = d25(main, a06, cluster_meta())
    exp = (len(om) - 10) / len(om)
    assert abs(r["Delta_om_R4_minus_R1"]["estimate"] - exp) < 1e-12 and r["Delta_om_R4_minus_R1"]["p"] < 0.05
    assert abs(r["D_om"]["estimate"] - exp) < 1e-12                       # tested because Delta_om significant
    assert r["correct_counterparts"] == {"from_main_run": len(inm), "from_a06": len(outm)}
    assert r["false_rejection_R0p"] == 0.0 and r["detection_R4_om"] == 1.0


def test_d26_synthetic():
    sub = r1live_subset()
    a06 = pd.DataFrame(_rows(sub, "R5post", "bait", [1] * 30 + [0] * 10, "R5POST"))   # SYNTHETIC
    main = pd.DataFrame(_rows(sub, "R1", "bait", [1] * 40, "MAIN")).drop(columns="check")
    rl = pd.Series(1.0, index=sub)
    r = d26(main, a06, cluster_meta(), rl)
    assert r["detection"] == {"R5post": 0.75, "R1": 1.0, "R1live": 1.0}
    t = r["R5post_minus_R1"]
    assert abs(t["estimate"] + 0.25) < 1e-12 and t["ci_low"] <= -0.25 <= t["ci_high"] and t["n_items"] == 40
