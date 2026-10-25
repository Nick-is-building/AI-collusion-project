"""A14 analysis (D37) on SYNTHETIC call lines and SYNTHETIC Study 2 verdict rows (labelled synthetic; no real
outcome is used)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analysis import a14_addendum as A
from scripts.analysis.a06_addendum import OMISSION_DIR, cluster_meta, load_stage
from scripts.analysis.a07_addendum import comparison_cells
from src.analysis.stats import holm
from src.replay.r6x import source_sentences
from src.runner.jobs import original_bob_message

OM = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))[:20]


def _line(item, variant, version, draw, verdict, reasoning="synthetic", stage="a14", check="LOOK", extra=None):
    cid = (f"{stage}:{check}:{item}:{variant}:{draw}" if check == "NAT"
           else f"{stage}:{check}:{item}:{variant}:{version}:{draw}")
    return dict(type="call", call_id=cid, stage=stage, mode="live", check=check, item_id=item, variant=variant,
                version=version, draw=draw, verdict=verdict, verdict_status="ok" if verdict else "missing_error",
                reasoning=reasoning, extra=extra, cost_usd=0.0)


def _look_lines():
    rid = {i: json.loads((OMISSION_DIR / f"{i}.json").read_text())["removed_id"] for i in OM}
    L = []
    for i, item in enumerate(OM):
        for d in (1, 2):
            # synthetic: R1 accepts every omission, R0' accepts; VIG rejects every omission naming the removed ID,
            # rejects the correct version on items 0-3 (FR 0.2); CHK = R1 on odd items, rejects on even items;
            # R4+VIG rejects; one CHK draw missing on item 1
            L.append(_line(item, "R1", "omission", d, "accept", stage="a06", check="OMIT"))
            L.append(_line(item, "R0p", "correct", d, "accept", stage="a06", check="OMIT"))
            L.append(_line(item, "R4", "omission", d, "reject" if i % 2 == 0 else "accept", stage="a06", check="OMIT"))
            L.append(_line(item, "VIG", "omission", d, "reject", f"{rid[item]} is left out"))
            L.append(_line(item, "VIG", "correct", d, "reject" if i < 4 else "accept"))
            L.append(_line(item, "CHK", "omission", d, None if (i == 1 and d == 1) else ("reject" if i % 2 == 0 else "accept")))
            L.append(_line(item, "CHK", "correct", d, "accept"))
            L.append(_line(item, "R4+VIG", "omission", d, "reject"))
    return L


def _r6x_extra(first, final, classification):
    return {"r6x": dict(first_verdict=first, final_verdict=final, gate_fired=False,
                        first_check=dict(compliant=True, compliant_ignoring_extra=True, missing=[], duplicated=[],
                                         n_extra=0, bad_labels=[]),
                        first_classification=classification), "first_reasoning": "synthetic"}


def test_look_primary_holm_gatekeeping_and_rows(tmp_path):
    (tmp_path / "syn.jsonl").write_text("\n".join(json.dumps(x) for x in _look_lines()) + "\n")
    a14 = A.load_a14(Path(tmp_path))
    a06 = load_stage("a06", Path(tmp_path))
    comp = comparison_cells(pd.DataFrame(columns=a14.columns).assign(check=[]), a06)
    a08 = pd.DataFrame({"variant": ["R6x"] * 20, "version": ["omission"] * 20, "item_id": OM,
                        "r6x_first_y": [1.0] * 20})
    meta = cluster_meta()
    r = A.look_section(a14[a14.check == "LOOK"], comp, a06, a08, meta)
    p = r["primary"]
    assert abs(p["L1"]["estimate"] - 1.0) < 1e-12 and abs(p["L2"]["estimate"] - 0.5) < 1e-12
    assert p["L1"]["n_items"] == 20 and p["L2"]["n_items"] == 20
    assert p["L1"]["p_holm"] == holm({"L1": p["L1"]["p"], "L2": p["L2"]["p"]})["L1"]
    for t in ("L1", "L2"):
        assert p[t]["p_holm"] >= p[t]["p"]
        assert p[f"D_{t}"]["tested"] is p[t]["significant"]
    assert p["L1"]["significant"]
    assert abs(p["D_L1"]["estimate"] - 0.8) < 1e-12          # [1 - FR(VIG)] - [0 - 0]; FR(VIG) = 0.2
    assert r["missing"] == 1
    assert abs(r["primary_missing_as_reject"]["L2"]["estimate"] - (0.5 + 0.5 / 20)) < 1e-12
    assert abs(r["primary_missing_as_accept"]["L2"]["estimate"] - 0.5) < 1e-12
    s = r["secondary"]
    assert abs(s["FR_VIG_minus_R0p"]["estimate"] - 0.2) < 1e-12 and s["FR_CHK_minus_R0p"]["estimate"] == 0.0
    assert abs(s["CHK_minus_R6x_first"]["estimate"] - (-0.5)) < 1e-12
    assert s["gap_under_cue_R4VIG_minus_VIG"]["estimate"] == 0.0
    assert s["gap_under_cue_R4VIG_minus_VIG"]["ci_low"] == 0.0 and s["gap_under_cue_R4VIG_minus_VIG"]["ci_high"] == 0.0
    assert abs(s["Delta_om_R4_minus_R1"]["estimate"] - 0.5) < 1e-12
    na = s["named_accept_and_right_reason"]
    assert na["VIG|omission"]["right_reason_rejects"] == 40 and na["VIG|omission"]["named_accept_calls"] == 0
    assert na["CHK|omission"]["rejects"] == 20 and na["CHK|omission"]["right_reason_rejects"] == 0
    rows = r["interpretation_rows"]
    assert rows["R2_L1_sig_FR_rises_more_than_0p05"] and not rows["R1_L1_sig_FR_within_0p05"]
    assert rows["R5_gap_under_cue_inside_0p10"] and not rows["R5_otherwise_gap_persists_under_vigilance"]
    assert not rows["R3_L1_null_L2_sig"] and not rows["R4_both_null"]
    json.dumps(r, default=str)


def test_look_rows_null_branches():
    prim = {"L1": {"significant": False}, "L2": {"significant": True}}
    sec = {"FR_VIG_minus_R0p": {"estimate": 0.0},
           "gap_under_cue_R4VIG_minus_VIG": {"estimate": 0.2, "ci_low": 0.05, "ci_high": 0.3}}
    r = A.look_rows(prim, sec)
    assert r["R3_L1_null_L2_sig"] and not r["R4_both_null"] and r["R5_otherwise_gap_persists_under_vigilance"]
    prim["L2"]["significant"] = False
    assert A.look_rows(prim, sec)["R4_both_null"]


def test_nat_test_labels_and_rows(tmp_path):
    recs = A.nat_records()
    items = list(dict.fromkeys(recs.item_id))
    L = []
    for i, item in enumerate(items):
        row = pd.read_csv("data/derived/items/natural_error_set.csv").set_index("item_id").loc[item]
        src = source_sentences(original_bob_message(row.trace, int(row.ep_index))[1])
        miss = set(recs[(recs.item_id == item) & (recs.role == "missing")].sentence)
        for d in (1, 2, 3):
            # synthetic: N1f accepts all; R6x rejects on even items (missing labeled include) and accepts on odd
            # items (missing labeled exclude); one N1f draw missing on item 0
            lab = "include" if i % 2 == 0 else "exclude"
            cls = [{"sentence": s, "label": lab if s.strip() in miss else "exclude"} for s in src]
            v = "reject" if i % 2 == 0 else "accept"
            L.append(_line(item, "N1f", "natural", d, None if (i == 0 and d == 1) else "accept", check="NAT"))
            L.append(_line(item, "R6x", "natural", d, v, check="NAT", extra=_r6x_extra(v, v, cls)))
    (tmp_path / "syn.jsonl").write_text("\n".join(json.dumps(x) for x in L) + "\n")
    a14 = A.load_a14(Path(tmp_path))
    main = pd.DataFrame([dict(call_id=f"m:{i}", item_id=i, variant="N1", version="correct", draw=1, y=0.0,
                              reasoning="", verdict_status="ok", verdict="accept") for i in items])
    r = A.nat_section(a14[a14.check == "NAT"], main, cluster_meta())
    assert r["n_items"] == 26 and r["missing_N1f"] == 1
    t = r["test_R6x_first_minus_N1f"]
    assert abs(t["estimate"] - 13 / 26) < 1e-12 and t["n_items"] == 26
    assert abs(r["missing_as_reject"]["test_R6x_first_minus_N1f"]["estimate"] - (13 / 26 - (1 / 3) / 26)) < 1e-12
    labs = r["missing_record_labels"]["per_call_record"]
    n_inc = 3 * int(sum((recs.role == "missing") & recs.item_id.isin(items[0::2])))
    assert labs.get("include", 0) == n_inc and labs.get("exclude", 0) == 3 * 44 - n_inc
    cat = r["detection_by_call_label_category"]
    assert cat["include"]["detection"] == 1.0 and cat["exclude"]["detection"] == 0.0
    assert set(cat) <= {"include", "exclude", "no missing record"}
    assert r["drift_N1f_minus_original_N1"]["estimate"] == 0.0
    ra = r["recognise_and_approve"]["R6x_list_missing_labeled_include_among_first_accepts"]
    assert ra["accepts_with_a_missing_record_labeled_include"] == 0
    assert r["records"]["flagged_not_in_source_or_transmitted"] == [["rep010_e08_alice", "extra", "REC18-cdbdd8"]]
    assert set(r["detection_by"]["error_type"]) == {"omission", "commission", "both"}
    rows = r["interpretation_rows"]
    assert rows["N1_significant_positive"] is r["significant"]
    json.dumps(r, default=str)


def test_study2_evidence_pairing_and_exclusion():
    rng = np.random.default_rng(1)
    rows = []
    for seq in range(1, 11):
        for arm in ("Aprime", "B", "Cprime", "PC"):
            for ep in range(0, 10):
                for judge in ("alice", "bob"):
                    # synthetic: seq 1 has no incorrect peer task in B; peer incorrect when ep in (5, 6)
                    inc = ep in (5, 6) and not (seq == 1 and arm == "B")
                    acc = (not inc) or (arm != "Aprime") or bool(rng.integers(0, 2) and judge == "alice")
                    rows.append(dict(seq=seq, arm=arm, episode_index=ep, judge=judge, peer_correct=not inc, accept=acc))
    rows = pd.DataFrame(rows)
    e = A.evidence_per_seq(rows, "B")
    assert np.isnan(e.loc[1, "p_inc"]) and e.loc[2, "p_inc"] == 1.0 and e.loc[2, "n_inc"] == 4
    ea = A.evidence_per_seq(rows, "Aprime")
    res = A.study2_evidence(rows)
    c = res["B_vs_Aprime"]
    assert c["E1_p_inc"]["n"] == 9 and c["E1_p_inc"]["n_excluded"] == 1 and c["E1_p_inc"]["excluded_seqs"] == [1]
    exp = float((1.0 - ea.p_inc.loc[2:]).mean())
    assert abs(c["E1_p_inc"]["mean_d"] - exp) < 1e-12
    exp2 = float(((1.0 - 1.0) - (ea.p_cor - ea.p_inc)).loc[2:].mean())
    assert abs(c["E2_disc"]["mean_d"] - exp2) < 1e-12
    assert c["seqs_without_incorrect_peer_task"]["B"] == [1]
    assert res["E2_bootstrap_upper_bound"] == c["E2_disc"]["ci95_bootstrap"]["hi"]
    assert "at most" in res["statement"] and "protocol violation" in res["label"]
    pc = res["descriptive"]["PC_alice_vs_Aprime_alice"]
    assert pc["judge"] == "alice"
    assert abs(pc["means"]["Aprime"]["p_inc"] - float(A.evidence_per_seq(rows, "Aprime", "alice").p_inc.mean())) < 1e-12


def test_partial_run_without_r6x_lines(tmp_path):
    """A partial run with NAT N1f lines but no R6x line yet must not raise (A15 finding, DEVLOG 05)."""
    item = A.nat_records().item_id.iloc[0]
    (tmp_path / "syn.jsonl").write_text(json.dumps(_line(item, "N1f", "natural", 1, "accept", check="NAT")) + "\n")
    a14 = A.load_a14(Path(tmp_path))
    assert "r6x_first_y" in a14 and a14.r6x_first_y.isna().all()
    main = pd.DataFrame(columns=["call_id", "item_id", "variant", "version", "draw", "y", "reasoning"])
    r = A.nat_section(a14[a14.check == "NAT"], main, cluster_meta())
    assert r["calls"] == 1 and r["test_R6x_first_minus_N1f"]["n_items"] == 0
