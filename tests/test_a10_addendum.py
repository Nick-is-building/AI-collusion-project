"""A10 analysis (D32-D34) on SYNTHETIC call lines (labelled synthetic; no real outcome is used)."""
import json
from pathlib import Path

import pandas as pd

from scripts.analysis import a10_addendum as A
from scripts.analysis.a06_addendum import OMISSION_DIR, cluster_meta, load_stage
from scripts.analysis.a07_addendum import comparison_cells


def _line(item, variant, version, draw, verdict, reasoning="synthetic", stage="a10", check="INC"):
    return dict(type="call", call_id=f"{stage}:{check}:{item}:{variant}:{version}:{draw}", stage=stage, mode="live",
                check=check, item_id=item, variant=variant, version=version, draw=draw, verdict=verdict,
                verdict_status="ok" if verdict else "missing_error", reasoning=reasoning, extra=None, cost_usd=0.0)


def _write(tmp_path, n_items=20):
    om = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))[:n_items]
    rid = {i: json.loads((OMISSION_DIR / f"{i}.json").read_text())["removed_id"] for i in om}
    L = []
    for i, item in enumerate(om):
        for d in (1, 2, 3):
            # synthetic: INC-R and SIG-N always reject the omission; INC-C accepts it on even items and names the
            # removed ID there; SIG-A = SIG-N; INC-A rejects; one INC-R draw missing on item 0
            L.append(_line(item, "INC-R", "omission", d, None if (i == 0 and d == 1) else "reject"))
            L.append(_line(item, "INC-C", "omission", d, "accept" if i % 2 == 0 else "reject",
                           f"{rid[item]} is excluded, fine" if i % 2 == 0 else "synthetic"))
            L.append(_line(item, "INC-A", "omission", d, "reject"))
            L.append(_line(item, "SIG-N", "omission", d, "reject", "you will accept my task", check="SIG"))
            L.append(_line(item, "SIG-A", "omission", d, "reject", check="SIG"))
        for d in (1, 2):
            for v in ("INC-R", "INC-C", "INC-A"):
                L.append(_line(item, v, "correct", d, "accept", "the reward rule says"))
            for v in ("SIG-N", "SIG-A"):
                L.append(_line(item, v, "correct", d, "accept", check="SIG"))
            L.append(_line(item, "R1", "omission", d, "accept", stage="a06", check="OMIT"))
            L.append(_line(item, "R0p", "correct", d, "accept", stage="a06", check="OMIT"))
    (tmp_path / "syn.jsonl").write_text("\n".join(json.dumps(x) for x in L) + "\n")
    return om


def test_primary_family_on_synthetic_lines(tmp_path):
    om = _write(tmp_path)
    a10c = load_stage("a10", Path(tmp_path))
    comp = comparison_cells(pd.DataFrame(columns=a10c.columns).assign(check=[]), load_stage("a06", Path(tmp_path)))
    info = A.items().loc[om]
    r = A.analyze_frames(a10c, comp, cluster_meta(), info)
    p = r["primary"]
    assert abs(p["T1"]["estimate"] - (-0.5)) < 1e-12 and p["T1"]["n_items"] == 20
    assert abs(p["T2"]["estimate"]) < 1e-12 and p["T2"]["p"] == 1.0 and not p["T2"]["significant"]
    assert abs(p["T3"]["estimate"] - 0.5) < 1e-12
    for t in ("T1", "T2", "T3"):
        assert p[t]["p_holm"] >= p[t]["p"]
    # gatekeeping: D tested only for a significant T
    assert p["D_T2"]["tested"] is False
    assert p["D_T1"]["tested"] is p["T1"]["significant"]
    assert abs(p["D_T1"]["estimate"] - (-0.5)) < 1e-12           # correct versions all accept
    # missing sensitivity: item 0's missing INC-R draw coded ACCEPT lowers INC-R detection there
    assert r["missing"] == 1
    assert r["primary_missing_as_accept"]["T1"]["estimate"] > p["T1"]["estimate"]
    assert abs(r["primary_missing_as_reject"]["T1"]["estimate"] - p["T1"]["estimate"]) < 1e-12
    arm = r["per_arm"]
    assert arm["INC-C"]["named_accept_calls_omission"] == 30 and arm["INC-R"]["named_accept_calls_omission"] == 0
    assert arm["INC-C"]["reward_mention"] == {"omission": "0/60", "correct": "40/40"}
    assert arm["SIG-N"]["reciprocity_mention"]["omission"] == "60/60"
    assert arm["R1"]["detection"]["estimate"] == 0.0
    assert abs(arm["INC-R"]["minus_R1_omission"]["estimate"] - 1.0) < 1e-12
    assert arm["INC-C"]["false_rejection"]["estimate"] == 0.0 and arm["INC-C"]["discrimination"] == 0.5
    assert set(r["per_arm_by_alice_correct"]) <= {"True", "False"}
    assert sum(v["n_items"] for v in r["per_arm_by_alice_correct"].values()) == 20
    rd = r["named_accept_reading"]
    assert rd["n_marker_positive_accepts"] == 30 and all(c["variant"] == "INC-C" for c in rd["calls"])
    assert "INC-A_minus_INC-R" in arm["secondary_contrasts"] and "SIG-R_minus_SIG-N" not in arm["secondary_contrasts"]
    json.dumps(r, default=str)   # serializable


def test_items_table():
    info = A.items()
    assert len(info) == 50 and info.bob_states_intent.sum() == 2
    assert info.alice_correct.dtype == bool


def test_recognise_approve_consistent_with_a07_a08():
    """Real raw data (no synthetic): the list channel agrees with the A07/A08 analyses' own counts."""
    from pathlib import Path as _P
    from scripts.analysis import recognise_approve as R
    from scripts.analysis.a07_addendum import load_a07
    from scripts.analysis.a08_addendum import load_a08
    lst = {r["source"]: r for r in R.list_channel()}
    a07 = load_a07()
    s = a07[(a07.variant == "R6s") & (a07.version == "omission")]
    assert lst["a07"]["calls"] == len(s) and lst["a07"]["accepts"] == int((s.r6s_first_y == 0).sum())
    a08 = load_a08()
    s = a08[(a08.variant == "R6x") & (a08.version == "omission")]
    assert lst["a08"]["accepts"] == int((s.r6x_first_y == 0).sum())
    assert lst["a08"]["named_accepts"] + lst["a08"]["not_named_accepts"] == lst["a08"]["accepts"]
    live = R.live_channel()[0]
    assert live["calls"] == 40 and live["accepts"] + live["rejects"] + live["missing"] == 40
    assert _P(R.__file__).exists()
