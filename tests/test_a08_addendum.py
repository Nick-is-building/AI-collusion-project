"""A08 analysis (D30 R6x, D31): loader columns, removed-sentence labels, and the pre-specified contrast on
SYNTHETIC call lines (labelled synthetic; no real outcome is used)."""
import json
from pathlib import Path

import pandas as pd

from scripts.analysis import a08_addendum as A
from scripts.analysis.a06_addendum import OMISSION_DIR, cluster_meta, load_stage
from scripts.analysis.a07_addendum import comparison_cells
from src.replay.r6x import check, source_sentences


def _classif(item, removed_label):
    o = json.loads((OMISSION_DIR / f"{item}.json").read_text())
    return [{"sentence": s, "label": removed_label if s == o["removed_sentence"] else "exclude"}
            for s in source_sentences(o["omission_raw_log"])], o["omission_raw_log"]


def _line(item, variant, version, draw, first, classif=None, raw=None, stage="a08", check_name="R6X"):
    extra = None
    if variant == "R6x":
        extra = {"r6x": {"first_verdict": first, "final_verdict": first, "retry_verdict": None, "gate_fired": False,
                         "first_check": check(classif, raw), "first_classification": classif},
                 "first_reasoning": "synthetic"}
    if variant == "R6":
        extra = {"r6": {"first_verdict": first, "final_verdict": first, "retry_verdict": None, "gate_fired": False,
                        "first_check": {"compliant": True}}, "first_reasoning": "synthetic"}
    return dict(type="call", call_id=f"{stage}:{check_name}:{item}:{variant}:{version}:{draw}", stage=stage,
                mode="live", check=check_name, item_id=item, variant=variant, version=version, draw=draw,
                verdict=first, verdict_status="ok", reasoning="synthetic", extra=extra, cost_usd=0.0)


def test_contrast_on_synthetic_lines(tmp_path):
    om = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))[:12]
    lines = []
    for i, item in enumerate(om):
        inc, raw = _classif(item, "include")
        exc, _ = _classif(item, "exclude")
        for d in (1, 2):
            # synthetic: R6x rejects whenever the removed sentence is labeled include (even items)
            lines.append(_line(item, "R6x", "omission", d, "reject" if i % 2 == 0 else "accept",
                               inc if i % 2 == 0 else exc, raw))
            lines.append(_line(item, "R6x", "correct", d, "accept", exc[1:], raw))   # non-compliant (missing one)
            lines.append(_line(item, "R6", "correct", d, "reject" if i == 0 else "accept", check_name="R6COR"))
            lines.append(dict(_line(item, "R1", "omission", d, "accept"), extra=None, check="OMIT", stage="a06",
                              call_id=f"a06:OMIT:{item}:R1:omission:{d}"))
            lines.append(dict(_line(item, "R0p", "correct", d, "accept"), extra=None, check="OMIT", stage="a06",
                              call_id=f"a06:OMIT:{item}:R0p:correct:{d}"))
    (tmp_path / "syn.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    a08 = A.load_a08(Path(tmp_path))
    assert set(a08.variant) == {"R6x", "R6"} and a08[a08.variant == "R6x"].r6x_first_y.notna().all()
    comp = comparison_cells(pd.DataFrame(columns=a08.columns).assign(check=[]), load_stage("a06", Path(tmp_path)))
    r = A.r6x_section(a08, comp, cluster_meta())
    t = r["test_R6x_first_minus_R1_omission"]
    assert r["detection_R6x_first"]["estimate"] == 0.5 and r["detection_R1"]["estimate"] == 0.0
    assert abs(t["estimate"] - 0.5) < 1e-12 and t["n_items"] == 12
    by = r["detection_by_removed_sentence_label"]["by_label"]
    assert by["include"] == dict(calls=12, first_rejects=12, detection=1.0, items=6, trajectories=by["include"]["trajectories"])
    assert by["exclude"]["detection"] == 0.0
    c = r["first_submission_compliance"]
    assert c["omission"]["first_compliance_rate"] == 1.0 and c["correct"]["first_compliance_rate"] == 0.0
    assert c["correct"]["with_missing"] == 24 and c["all"]["field_absent"] == 0
    r6 = A.r6_correct_section(a08, comp, cluster_meta())
    assert abs(r6["false_rejection_first"]["estimate"] - 1 / 12) < 1e-12 and r6["calls"] == 24
