"""A07 analysis (D28 R6s): loader columns, enumeration matching, and the pre-specified contrast on SYNTHETIC
call lines (labelled synthetic; no real outcome is used)."""
import json

from scripts.analysis import a07_addendum as A
from scripts.analysis.a06_addendum import cluster_meta


def _line(item, variant, version, draw, first, final=None, items=None, stage="a07"):
    extra = {"r6s": {"first_verdict": first, "final_verdict": final or first, "retry_verdict": None,
                     "gate_fired": False, "first_check": {"compliant": True, "n_listed": len(items or [])},
                     "first_source_items": items}, "first_reasoning": "synthetic"}
    return dict(type="call", call_id=f"{stage}:R6S:{item}:{variant}:{version}:{draw}", stage=stage, mode="live",
                check="R6S", item_id=item, variant=variant, version=version, draw=draw, verdict=final or first,
                verdict_status="ok", reasoning="synthetic", extra=extra, cost_usd=0.0)


def test_listed_removed():
    assert A._listed_removed(json.dumps(["A b.", "The  Removed sentence."]), "the removed sentence.")
    assert A._listed_removed(json.dumps(["x"]), "y") is False
    assert A._listed_removed("null", "y") is None


def test_contrast_on_synthetic_lines(tmp_path):
    from pathlib import Path
    om = sorted(p.stem for p in A.OMISSION_DIR.glob("rep*_alice.json"))[:12]
    lines = []
    for i, item in enumerate(om):
        for d in (1, 2):
            lines.append(_line(item, "R6s", "omission", d, "reject", items=["s"]))
            lines.append(_line(item, "R6s", "correct", d, "accept", items=["s"]))
            # synthetic comparison cells: R1 detects half the items, R0' never rejects
            lines.append(dict(_line(item, "R1", "omission", d, "reject" if i % 2 else "accept"), extra=None,
                              check="OMIT", stage="a06", call_id=f"a06:OMIT:{item}:R1:omission:{d}"))
            lines.append(dict(_line(item, "R0p", "correct", d, "accept"), extra=None, check="OMIT", stage="a06",
                              call_id=f"a06:OMIT:{item}:R0p:correct:{d}"))
    (tmp_path / "syn.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    a07 = A.load_a07(Path(tmp_path))
    assert a07.r6s_first_y.notna().all() and set(a07.variant) == {"R6s"}
    from scripts.analysis.a06_addendum import load_stage
    import pandas as pd
    comp = A.comparison_cells(pd.DataFrame(columns=a07.columns).assign(check=[]), load_stage("a06", Path(tmp_path)))
    r = A.r6s_section(a07, comp, cluster_meta())
    t = r["test_R6s_first_minus_R1_omission"]
    assert r["detection_R6s_first"] == 1.0 and r["detection_R1"] == 0.5 and abs(t["estimate"] - 0.5) < 1e-12
    assert r["false_rejection_R6s_first"] == 0.0 and r["false_rejection_R0p"] == 0.0
    assert r["enumeration_completeness"]["by_listed_removed"]["not listed"]["calls"] == 24
