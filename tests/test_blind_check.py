"""Blind-check package generator (plan 8.3 rule 4), exercised on a small n inside scratch/."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from src.blind_check.make_package import BAITS, allocate, make

OUT = Path(__file__).resolve().parents[1] / "scratch" / "pytest_blind_check"


def test_package_structure_and_key_hash():
    shutil.rmtree(OUT, ignore_errors=True)
    n = min(5, len(list(BAITS.glob("*.json"))))
    res = make(n, OUT)
    key_bytes = (OUT / "key.local.json").read_bytes()
    assert hashlib.sha256(key_bytes).hexdigest() == res["key_sha256"]
    key = json.loads(key_bytes)
    pairs = sorted((OUT / "pairs").glob("*.md"))
    assert len(pairs) == n == len(key["pairs"])
    for p in pairs:
        text = p.read_text()
        k = key["pairs"][p.stem]
        assert "bait" not in text.lower() and k["item_id"] not in text   # no label leak
        a = text.split("## Version A")[1].split("## Version B")[0]
        b = text.split("## Version B")[1]
        bait_part = a if k["bait_version"] == "A" else b
        other = b if k["bait_version"] == "A" else a
        assert k["bait_id"] in bait_part and k["bait_id"] not in other
        # identical layout: same step headings and the same folded blocks in A and B
        import re
        heads = lambda part, L: [re.sub(rf"\b{L}\b", "X", h) for h in re.findall(r"^### .*$", part, re.M)]
        assert heads(a, "A") == heads(b, "B")
        assert a.count("<details>") == b.count("<details>")
        assert text.index("## The task") < text.index("## Version A") < text.index("## Version B")
    instr = (OUT / "INSTRUCTIONS.md").read_text()
    assert "bait" not in instr.lower() and all(v["item_id"] not in instr for v in key["pairs"].values())
    assert (OUT / "ANSWERS.md").exists()
    shutil.rmtree(OUT)


def test_refuses_with_too_few_baits():
    with pytest.raises(SystemExit):
        make(10_000, OUT)


def test_allocation_proportional():
    assert allocate({"data_search": 99, "record_extraction": 24}, 20) == {"data_search": 16, "record_extraction": 4}
    assert allocate({"a": 1, "b": 1}, 3) == {"a": 2, "b": 1}
    assert sum(allocate({"a": 7, "b": 5, "c": 3}, 10).values()) == 10
