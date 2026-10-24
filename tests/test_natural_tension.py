"""D29 (A07): natural-error tension tables are reproducible from the raw main-run and A06 call lines
and the committed tables; the N1/N4 totals match the A06 report (10/35 vs 5/35). No model call."""
from pathlib import Path

import pytest

from scripts.a07 import natural_tension as nt

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rerun(tmp_path_factory):
    d = tmp_path_factory.mktemp("d29")
    old = nt.FEATURES, nt.DISCORDANT
    nt.FEATURES, nt.DISCORDANT = d / "features.csv", d / "discordant.csv"
    try:
        totals, disc, feats = nt.main()
    finally:
        nt.FEATURES, nt.DISCORDANT = old
    return d, totals, disc, feats


def test_tables_reproducible(rerun):
    d, *_ = rerun
    assert (d / "features.csv").read_bytes() == (ROOT / "data/derived/rubric/natural_tension_features.csv").read_bytes()
    assert (d / "discordant.csv").read_bytes() == (ROOT / "data/derived/rubric/natural_tension_discordant.csv").read_bytes()


def test_totals_and_discordant(rerun):
    _, totals, disc, feats = rerun
    assert totals == {"N1_rejects": 10, "N4_rejects": 5, "n": 35}
    assert len(disc) == 9
    assert int((disc.N1 > disc.N4).sum()) == 7 and int((disc.N4 > disc.N1).sum()) == 2
    assert (feats.kind == "planted").sum() == 50
    assert feats[feats.kind == "planted"].sentence_in_read_source.all()
    assert not feats[feats.kind == "planted"].named_by_bob.any()   # D25 skips named records
