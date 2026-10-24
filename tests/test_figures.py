"""Figure data and paper figures (A07 task 3): Study 0 table provenance and grouping; figures draw from
the committed verification.json only."""
import json
from pathlib import Path

import pytest

from scripts.analysis import figure_data, figures

VERIF = Path(__file__).resolve().parents[1] / "results" / "summaries" / "verification.json"


def test_study0_hash_and_groups():
    s0 = figure_data.study0()
    assert s0["n_conditions"] == 53
    unc = sorted(r["condition"] for r in s0["conditions"] if r["group"] == "unconstrained")
    assert unc == ["communication__gemini-3-1-flash-lite__unconstrained", "communication__gemini-3-7-flash__unconstrained"]
    d = {r["condition"]: r["discrimination"] for r in s0["conditions"]}
    assert round(d[unc[0]], 3) == 0.107 and round(d[unc[1]], 3) == 0.047      # plan 2.3
    assert round(s0["median"], 3) == 0.053 and round(s0["max"], 3) == 0.155


def test_figures_from_verification(tmp_path, monkeypatch):
    if "figure_data" not in json.loads(VERIF.read_text()):
        pytest.skip("verification.json has no figure_data yet")
    monkeypatch.setattr(figures, "OUT", tmp_path)
    monkeypatch.setattr(figures, "ROOT", tmp_path)
    written = figures.main(["--verification", str(VERIF)])
    assert len(written) == 8 and all((tmp_path / Path(w).name).stat().st_size > 1000 for w in written)
