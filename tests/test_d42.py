"""D42: accept-class table covers exactly the omission ACCEPTs of the D42 cells; Wilson intervals; figure data path."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.analysis import d42_accept_classes as D
from scripts.figures import fig_verifier_transfer as F

ROOT = Path(__file__).resolve().parents[1]


def test_wilson_known_values():
    lo, hi = D.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-4)
    lo, hi = D.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)
    assert D.wilson(0, 0) == (None, None)


def test_csv_covers_exactly_the_accepts():
    rows = list(csv.DictReader(D.CSV.open(encoding="utf-8")))
    acc = {a["call_id"]: a for a in D.accepts()}
    assert sorted(r["call_id"] for r in rows) == sorted(acc)
    assert all(r["category"] in D.CATEGORIES and r["quote_or_note"].strip() for r in rows)
    assert all((r["model"], r["cell"]) == (acc[r["call_id"]]["model"], acc[r["call_id"]]["cell"]) for r in rows)
    excl = set(json.loads(D.EXCLUSIONS.read_text())["excluded"])
    assert not any(a["item_id"] in excl for a in acc.values())


def test_summary_counts_add_up():
    res = D.summarize()
    for k, e in res["cells"].items():
        assert sum(e[c]["count"] for c in D.CATEGORIES) == e["accepts"] <= e["calls"]


def test_figure_reads_verification_and_writes(tmp_path):
    v = json.loads(F.VERIFICATION.read_text())
    data = F.series(v)
    assert set(data) == {c for c, _ in F.DETECTION + F.FALSE_REJECTION}
    assert all(len(x) == 3 and "estimate" in x[0] for x in data.values())
    paths = F.build(v, tmp_path)
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
    bad = json.loads(json.dumps(v))
    bad["addendum"]["a17"]["primary_item_set"]["haiku_minus_flash_lite"]["cells"]["R1|omission"]["flash_lite"]["estimate"] = 0.0
    with pytest.raises(ValueError):
        F.series(bad)
