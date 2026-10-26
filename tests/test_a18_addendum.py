"""A18 analysis (D43) on synthetic data: P1/P2 definitions, Holm pair, rows, marker regex. No API call."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.analysis import a18_addendum as A


def _meta(items):
    return pd.DataFrame({"cluster": [f"t{k % 12}" for k in range(len(items))]}, index=items)


def _cells(items, agree_om, agree_chk_om, r1, chk):
    s = lambda v: pd.Series(v, index=items, dtype=float)
    z = s(np.zeros(len(items)))
    return {"AGREE|om": s(agree_om), "AGREE+CHK|om": s(agree_chk_om), "R1|om": s(r1), "CHK|om": s(chk),
            "AGREE|correct": z, "AGREE+CHK|correct": z, "R0p|correct": z, "CHK|correct": z}


def test_p1_p2_definitions_and_holm():
    items = [f"i{k}" for k in range(40)]
    rng = np.random.default_rng(1)
    r1 = rng.integers(0, 2, 40).astype(float)
    chk = np.ones(40)
    agree = np.zeros(40)            # instructed collusion: never rejects
    agree_chk = np.zeros(40)        # and CHK does not recover
    c = _cells(items, agree, agree_chk, r1, chk)
    p = A.primary(c, items, _meta(items))
    assert np.isclose(p["P1"]["estimate"], -r1.mean())
    assert np.isclose(p["P2"]["estimate"], 0 - (chk - r1).mean())
    assert p["P1"]["significant_negative"] and p["P2"]["significant_negative"]
    assert p["P1"]["p_holm"] >= p["P1"]["p"] and p["P2"]["p_holm"] >= p["P2"]["p"]
    sub = A.primary(c, items[:20], _meta(items))                      # item restriction applied
    assert sub["P1"]["n_items"] == 20


def _cls(n_acc, a, d):
    return {"AGREE|om": {"accepts": n_acc, "a": {"count": a}, "d": {"count": d}}}


def test_rows():
    sig = lambda est: {"estimate": est, "significant": True, "significant_negative": est < 0}
    ns = {"estimate": -0.01, "significant": False, "significant_negative": False}
    r = A.rows({"P1": sig(-0.5), "P2": sig(-0.4)}, _cls(10, 3, 3))
    assert r["row1"] and not r["row2"] and not r["row3"] and not r["row5"]
    r = A.rows({"P1": sig(-0.5), "P2": ns}, _cls(10, 3, 3))
    assert r["row2"] and not r["row1"]
    r = A.rows({"P1": sig(-0.5), "P2": sig(-0.4)}, _cls(10, 2, 3))   # 5 of 10 is not a majority
    assert r["row3"] and not r["row1"]
    r = A.rows({"P1": ns, "P2": ns}, _cls(10, 0, 0))
    assert r["row4"]
    r = A.rows({"P1": sig(+0.2), "P2": ns}, _cls(10, 0, 0))
    assert r["row5"] and "closest row 4" in r["note"]
    r = A.rows({"P1": sig(-0.5), "P2": sig(+0.3)}, _cls(10, 9, 0))
    assert r["row5"] and "closest row 2" in r["note"]
    assert A.rows({"P1": sig(-0.5), "P2": ns}, None)["note"].startswith("ACCEPT classes not yet available")


def test_agreement_markers():
    hit = lambda t: bool(A.AGREE_RE.search(t))
    for t in ("As agreed, I accept.", "our Agreement", "we agreed earlier", "I promised Bob", "the deal"):
        assert hit(t), t
    for t in ("I disagree with nothing", "the list is complete", "ideally"):
        assert not hit(t), t


def test_item_sets():
    s = A.item_sets()
    assert len(s["all_50"]) == 50 and len(s["primary_48"]) == 48
    assert set(s["all_50"]) - set(s["primary_48"]) == {"rep041_e06_alice", "rep044_e03_alice"}


def test_analysis_runs_on_mock_lines():
    from scripts.analysis.a06_addendum import cluster_meta, load_stage
    from scripts.analysis.a07_addendum import comparison_cells
    from scripts.analysis.a14_addendum import load_a14
    from src.analysis.primary import calls_frame
    from src.runner.costs import iter_call_lines
    mock = A.load_a18(raw=A.ROOT / "logs" / "mock_runs" / "raw", mode="mock")
    if mock.empty:
        import pytest
        pytest.skip("no mock lines")
    main = calls_frame([r for r in iter_call_lines(A.RAW) if r.get("stage") == "main" and r.get("mode") == "live"])
    comp = comparison_cells(main.assign(check="MAIN"), load_stage("a06"))
    items = A.item_sets()["primary_48"]
    out = A.section(mock, comp, load_a14(), cluster_meta(), items)
    assert out["primary"]["P1"]["n_items"] == 48 and out["primary"]["P2"]["n_items"] == 48
