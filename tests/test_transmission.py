"""strict_full reproduces the 60 stored examples of the pre-sprint proof package (plan section 23.2)."""
import json
import zipfile
from pathlib import Path

import pytest

from src.reanalysis.transmission import coverage, strict_full, verbatim_prefix

ZIP = Path(__file__).resolve().parents[1] / "prior_work" / "1_reanalyse" / "nachweispaket_reanalyse.zip"


def samples():
    with zipfile.ZipFile(ZIP) as z:
        return [json.loads(l) for l in z.read("nachweis/stichprobe_uebertragung.jsonl").decode().splitlines()]


SAMPLES = samples()


def test_sample_count_and_categories():
    assert len(SAMPLES) == 60
    cats = {}
    for s in SAMPLES:
        cats[s["kategorie"]] = cats.get(s["kategorie"], 0) + 1
    assert cats == {"voll": 20, "fast_voll": 20, "teilweise": 20}


@pytest.mark.parametrize("i", range(60))
def test_strict_full_matches_stored_label(i):
    s = SAMPLES[i]
    assert strict_full(s["raw_log"], s["peer_messages"]) == s["label_strict_full"]
    # stored coverage is rounded to 4 decimals in the package
    assert round(coverage(s["raw_log"], s["peer_messages"]), 4) == s["label_coverage"]


def test_basic_semantics():
    raw = "abcdefghij"
    assert strict_full(raw, ["xx abcde yy", "fghij"])          # two pieces, framing allowed
    assert not strict_full(raw, ["abcde", "fghi"])             # tail missing
    assert not strict_full(raw, ["fghij", "abcde"])            # wrong order
    assert not strict_full(raw, ["abcde fghij"])               # one piece per message only
    assert not strict_full(raw, ["abcdeXfghij"])               # changed character
    assert verbatim_prefix(raw, []) == 0
    assert not strict_full("", ["anything"])
