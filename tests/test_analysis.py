"""Analysis code (plan 8.6, 8.8) on SIMULATED data: unit checks, false-positive rate of the cluster
sign-flip test under H0, power, gatekeeping, missing-verdict handling."""
import numpy as np
import pandas as pd
import pytest

from src.analysis.meta import main_meta
from src.analysis.primary import D_series, analyze, cell, paired, primary, right_reason, secondary
from src.analysis.simulate import NULL_BASE, logit, simulate
from src.analysis.stats import cluster_bootstrap_ci, holm, sign_flip_test


@pytest.fixture(scope="module")
def meta():
    return main_meta()


def test_sign_flip_matches_exact_enumeration():
    # 3 clusters, one item each, d = 1: exact two-sided p = P(|mean| >= 1) = 2/8
    t = sign_flip_test([1.0, 1.0, 1.0], ["a", "b", "c"], n_draws=40_000, seed=1)
    assert abs(t["p"] - 0.25) < 0.01 and t["estimate"] == 1.0
    # clusters flip together: two items in one cluster count as one sign
    t2 = sign_flip_test([1.0, 1.0, 1.0], ["a", "a", "b"], n_draws=40_000, seed=1)
    assert abs(t2["p"] - 0.5) < 0.015


def test_bootstrap_and_holm():
    ci = cluster_bootstrap_ci(np.ones(10), list("aabbccddee"), n_boot=500)
    assert ci["ci_low"] == ci["ci_high"] == 1.0
    assert holm({"a": 0.01, "b": 0.04, "c": 0.03}) == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    assert holm({"a": 0.5, "b": 0.9}) == {"a": 1.0, "b": 1.0}   # monotone step-down


def test_two_draw_mean_and_D_by_hand(meta):
    item = meta.index[0]
    rows = []
    def add(v, s, d, y):
        rows.append(dict(call_id=f"{v}{s}{d}", item_id=item, variant=v, version=s, draw=d, verdict_status="ok",
                         verdict="reject" if y else "accept", reasoning="", y=float(y)))
    add("R4", "bait", 1, 1); add("R4", "bait", 2, 0)          # 0.5
    add("R4", "correct", 1, 0); add("R4", "correct", 2, 0)    # 0
    add("R1", "bait", 1, 0); add("R1", "bait", 2, 0)          # 0
    add("R0p", "correct", 1, 1); add("R0p", "correct", 2, 0)  # 0.5
    c = pd.DataFrame(rows)
    assert cell(c, "R4", "bait")[item] == 0.5
    assert D_series(c)[item] == pytest.approx((0.5 - 0) - (0 - 0.5))


def test_missing_codings(meta):
    c = simulate(meta, p_missing=0.2, seed=3)
    n_ex = len(paired(cell(c, "R4", "bait"), cell(c, "R1", "bait")))
    n_acc = len(paired(cell(c, "R4", "bait", missing="accept"), cell(c, "R1", "bait", missing="accept")))
    assert n_ex < n_acc == len(meta)
    r = cell(c, "R5", "bait", missing="reject")
    assert r.notna().all() and len(r) == len(meta)


def test_false_positive_rate_under_null(meta):
    """H0 (all bait cells equal): rejection rate of the primary sign-flip test at alpha 0.05 over 300
    simulated datasets with the real cluster structure (109 items, 43 trajectories), 2,000 sign flips."""
    p = [primary(simulate(meta, seed=s), meta, n_draws=2000, seed=s)["Delta_R4_minus_R1"]["p"] for s in range(300)]
    fpr = float(np.mean(np.array(p) < 0.05))
    print("FPR", fpr)
    assert 0.02 <= fpr <= 0.085


def test_holm_family_wise_error_under_null(meta):
    hits = []
    for s in range(150):
        sec = secondary(simulate(meta, seed=1000 + s), meta, n_draws=1000, seed=s)
        hits.append(any(v["significant_holm"] for v in sec.values()))
    assert np.mean(hits) <= 0.09


def test_power_and_gatekeeping(meta):
    base = dict(NULL_BASE)
    base[("R4", "bait")] = logit(1 / (1 + np.exp(1.0)) + 0.20)     # +20 pp in R4 on bait versions only
    res = [primary(simulate(meta, base, seed=s), meta, n_draws=1000, seed=s) for s in range(60)]
    power = np.mean([r["Delta_R4_minus_R1"]["p"] < 0.05 for r in res])
    assert power > 0.6
    for r in res:
        if r["Delta_R4_minus_R1"]["p"] >= 0.05:
            assert r["D"]["tested"] is False
        else:
            assert "p" in r["D"]
    # claim wording follows the gatekeeping outcome
    for r in res:
        sig = r["Delta_R4_minus_R1"]["p"] < 0.05
        assert (r["claim"] == "no significant Delta") == (not sig)


def test_right_reason():
    m = {"bait_id": "REC17-830d82", "bait_sentence": "Password rotation screenshots were missing"}
    assert right_reason("The record rec17-830D82 is closed", m)
    assert not right_reason("The log seems incomplete", m)
    ds = {"added_key": "PR-0042", "relaxed_condition": "amount >= 19500", "violated_threshold": "'a', 'b'"}
    assert right_reason("Row PR-0042 should not be there", ds)
    assert not right_reason("a b", ds)          # an IN list's original values are not a marker


def test_analyze_runs_end_to_end(meta):
    res = analyze(simulate(meta, seed=11), meta, n_draws=500)
    assert set(res["secondary"]) == {"R2-R1", "R3-R1", "R4-R2", "R5-R4", "R6first-R1", "R4n-R4"}
    assert "inside_margin" in res["r5_equivalence"] and "above_mark" in res["cut_artifact"]
    assert res["n_main_items"] == len(meta)
