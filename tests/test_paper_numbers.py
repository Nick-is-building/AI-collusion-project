"""paper_numbers: every printed source key resolves in its summary file and the printed estimate equals it."""
import json
import re

from scripts.analysis import paper_numbers as P


def test_every_row_resolves_and_matches():
    raw = {k: (P.SUMMARIES / f).read_bytes() for k, f in P.SOURCES.items()}
    src = {k: json.loads(b) for k, b in raw.items()}
    text = P.build(src, {k: "test" for k in raw})
    flat = {k: P.flatten(v) for k, v in src.items()}
    rows = [l for l in text.splitlines() if l.startswith("| ") and l.endswith("` |")]
    cmp_rows = [l for l in text.splitlines() if l.startswith("| ") and "(fields estimate" in l]
    assert cmp_rows   # D40 comparison records, checked below
    for row in cmp_rows:
        key = re.findall(r"`([^`]+)`", row)[-1]
        s, path = key.split(":", 1)
        rec = flat[s][[k for k in flat[s] if k.replace("|", "/") == path][0]]
        sfx = {"(all)": ""}.get(row.split("|")[1].split()[-1], row.split("|")[1].split()[-1])
        cells = [c.strip() for c in row.strip("|").split("|")]
        e = rec.get(f"estimate{sfx}")
        assert cells[1] == (P.fmt(e) if not isinstance(e, float) else f"{e:.3f}"), row
    assert len(rows) > 1000
    for row in rows:
        key = re.findall(r"`([^`]+)`", row)[-1]
        s, path = key.split(":", 1)
        cand = [k for k in flat[s] if k.replace("|", "/") == path]
        assert cand, key
        v = flat[s][cand[0]]
        cells = [c.strip() for c in row.strip("|").split("|")]
        est = P.stat_cells(v)[0] if P._is_stat(v) else P.fmt(v)
        assert cells[1] == est, (row, est)
    for title, _ in P.SECTIONS:   # every requested section is present
        assert f"## {title}" in text
