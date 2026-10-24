"""results_tables: every printed key resolves in verification.json and the printed estimate equals it."""
import json
import re

from scripts.analysis.results_tables import VERIFICATION, Tables, build


def test_every_key_resolves_and_values_match():
    v = json.loads(VERIFICATION.read_text())
    t = Tables(v)
    text = build(v, "test")
    rows = [l for l in text.splitlines() if l.startswith("| ") and "`" in l]
    assert len(rows) > 100
    for row in rows:
        key = re.findall(r"`([^`]+)`", row)[-1]
        o = t.get(key)   # raises if the key does not exist
        cells = [c.strip() for c in row.strip("|").split("|")]
        if isinstance(o, dict) and "estimate" in o:
            assert t.num(o["estimate"]) in cells, row
        elif not isinstance(o, (dict, list)):
            assert t.num(o) in cells, row


def test_missing_key_raises():
    import pytest
    with pytest.raises(KeyError):
        Tables({"a": {}}).get("a.b")
