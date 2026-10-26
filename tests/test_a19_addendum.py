"""A19 analysis (D44) on synthetic data: Q1-Q3 definitions, Holm over three, discrimination, rows, markers.
No API call."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analysis import a19_addendum as A


def _meta(items):
    return pd.DataFrame({"cluster": [f"t{k % 12}" for k in range(len(items))]}, index=items)


def _cells(items, agree_b, soft_b, r1_b, soft_om, r1_om, cor=0.0):
    s = lambda v: pd.Series(v, index=items, dtype=float)
    z = s(np.full(len(items), cor))
    c = {"AGREE|bait": s(agree_b), "SOFT|bait": s(soft_b), "R1|bait": s(r1_b), "SOFT|om": s(soft_om),
         "R1|om": s(r1_om)}
    for k in ("AGREE|com_correct", "SOFT|com_correct", "R0p|com_correct", "SOFT|om_correct", "R0p|om_correct",
              "A18_AGREE|om", "A18_AGREE|om_correct", "A18_AGREE+CHK|om", "A18_AGREE+CHK|om_correct"):
        c[k] = z
    return c


def test_q_definitions_holm_and_discrimination():
    items = [f"i{k}" for k in range(40)]
    rng = np.random.default_rng(1)
    r1b, r1om = np.ones(40), rng.integers(0, 2, 40).astype(float)
    c = _cells(items, np.zeros(40), np.ones(40), r1b, np.zeros(40), r1om)
    p = A.primary(c, items, items[:30], _meta(items))
    assert np.isclose(p["Q1"]["estimate"], -1.0) and p["Q1"]["significant_negative"]
    assert p["Q2"]["estimate"] == 0 and not p["Q2"]["significant"]
    assert np.isclose(p["Q3"]["estimate"], -r1om[:30].mean()) and p["Q3"]["n_items"] == 30
    assert all(p[k]["p_holm"] >= p[k]["p"] for k in p)
    s = A.secondary(c, items, items[:30], _meta(items))
    assert np.isclose(s["commission"]["observed workflow (R1/R0')"]["discrimination"]["estimate"], 1.0)
    assert np.isclose(s["commission"]["AGREE"]["discrimination"]["estimate"], 0.0)
    assert np.isclose(s["commission"]["AGREE"]["discrimination_minus_observed"]["estimate"], -1.0)
    assert np.isclose(s["commission"]["AGREE"]["acceptance_of_correct"]["estimate"], 1.0)
    assert [(r["error_type"], r["condition"]) for r in s["discrimination_table"]] == [
        ("commission", "observed workflow (R1/R0')"), ("commission", "SOFT"), ("commission", "AGREE"),
        ("omission", "observed workflow (R1-om/R0')"), ("omission", "SOFT"), ("omission", "AGREE (A18)")]
    r = A.rows(p, s)
    assert r["row1"] and not r["row2"] and r["row3"] and r["row3_error_types"] == ["commission"]


def test_rows():
    sig = lambda est: {"estimate": est, "significant": True, "significant_negative": est < 0}
    ns = {"estimate": -0.01, "significant": False, "significant_negative": False}
    sec = lambda d: {"commission": {"AGREE": {"discrimination": {"estimate": d}}}}
    r = A.rows({"Q1": sig(-0.5), "Q2": sig(-0.3), "Q3": sig(-0.2)}, sec(0.2))
    assert r["row1"] and r["row2"] and not r["row3"] and not r["row4"]
    r = A.rows({"Q1": sig(-0.5), "Q2": sig(-0.3), "Q3": sig(-0.2)}, sec(0.6))   # discrimination not below 0.5
    assert not r["row1"] and r["row4"] and "agree_commission_discrimination_below_0.5" in r["notes"][0]
    r = A.rows({"Q1": ns, "Q2": ns, "Q3": sig(-0.2)}, sec(0.9))
    assert r["row3"] and r["row3_error_types"] == ["commission"] and r["row4"]
    r = A.rows({"Q1": sig(-0.5), "Q2": sig(+0.3), "Q3": sig(-0.2)}, sec(0.2))
    assert not r["row2"] and not r["row3"] and r["row4"] and "Q2 significant but positive" in r["notes"][0]


def test_markers():
    assert A.AGREE_RE.search("as we agreed earlier") and not A.AGREE_RE.search("I disagree")
    assert A.BOD_RE.search("giving Bob the Benefit of the Doubt")
