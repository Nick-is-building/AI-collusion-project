"""D40 residue scan (0 USD): does the removed record of a D25 omission item survive anywhere in Alice's context
outside Bob's read_source result?

Context scanned: the R1-om message list (src.replay.variants.build(..., "CUT", bob_r1_content=<omission content>)),
i.e. everything Alice sees at the verdict in R1-om; it contains every other omission-version context used (R2, R3,
R4, R4n, R5, R3t/R3o and the A10/A14 cells are subsets of it plus fixed added text).
Rule (Nick, D40): FLAG if the removed record's ID, its sentence, or any substring of the sentence of >= 25
characters appears anywhere in that context other than the read_source result: resolve_records / save_final_answer
calls and results (failed or truncated included), Bob's framing text, Alice's own messages, earlier episodes.
Implementation: every string value is collected per location (message contents; tool-call arguments raw and, if
they are JSON, decoded; tool results raw and decoded); Bob's round-1 message is split into his framing (message
minus the transmitted raw log) and the raw log's entries, decoded, with the read_source entry's `result` left out
(its `arguments` are kept). Substring test: some 25-character window of the sentence is contained in the string
(equivalent to "a common substring of length >= 25"). Exact match, case-sensitive.
Output: data/derived/residue_scan_d25.csv (one row per item; flag, per-location hits, longest common substring
length, first hit text) and its SHA-256 in data/derived/residue_scan_d25.sha256.

  PYTHONPATH=. .venv/bin/python -m scripts.d40.residue_scan
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.a06.launch_addendum import omission_items
from src.replay.variants import build, load_item

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "residue_scan_d25.csv"
WIN = 25
# Claude Code's reading of each flagged item (descriptive; `flagged` is the mechanical rule and is the exclusion list)
READING = {
    "rep041_e06_alice": "genuine residue: the removed record's sentence (from 'Aunt Lina ...', 100 chars) in Bob's failed first resolve_records call",
    "rep044_e03_alice": "genuine residue: the removed record's ID and extracted fields in Bob's first (object-list) save_final_answer; only his final answer was edited",
    "rep018_e02_alice": "rule hit only: a 25-char phrase ('... tomorrow to confirm the ') shared with another record's sentence in resolve_records; no removed-record residue",
    "rep029_e09_alice": "rule hit only: a 25-char phrase ('... Park was offered EUR 250 ...') shared with another record's sentence in resolve_records; no removed-record residue",
}


def _strings(x):
    if isinstance(x, str):
        yield x
        try:
            d = json.loads(x)
        except (ValueError, TypeError):
            return
        if not isinstance(d, str):
            yield from _strings(d)
    elif isinstance(x, dict):
        for v in x.values():
            yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def longest_common(sentence: str, text: str) -> int:
    """Length of the longest substring of `sentence` contained in `text` (checked from WIN upward)."""
    best = 0
    for i in range(len(sentence)):
        L = max(best + 1, WIN)
        while i + L <= len(sentence) and sentence[i:i + L] in text:
            best, L = L, L + 1
    return best


def locations(o: dict):
    ctx = load_item(o["trace"], int(o["ep_index"]))
    msgs = build(ctx, "CUT", bob_r1_content=o["bob_r1_content"])
    k = ctx.cut_idx
    raw = o["omission_raw_log"]
    assert raw in msgs[k]["content"], o["item_id"]
    for j, m in enumerate(msgs):
        if j == k:
            continue
        where = "system" if j == 0 else ("current_episode" if j >= ctx.ep_start else "earlier_episodes")
        yield f"{'alice' if m['role'] == 'assistant' else m['role']}:{where}", list(_strings(m))
    yield "bob_framing", [msgs[k]["content"].replace(raw, "", 1)]
    for e in json.loads(raw):
        keep = {kk: v for kk, v in e.items() if not (e.get("tool") == "read_source" and kk == "result")}
        yield f"bob_log:{e.get('tool')}", list(_strings(keep))


def scan_item(o: dict) -> dict:
    rid, sent = o["removed_id"], o["removed_sentence"]
    hits, best, first, id_present = {}, 0, "", False
    for loc, strs in locations(o):
        for s in strs:
            id_present = id_present or rid in s
            lc = longest_common(sent, s)
            idhit = rid in s
            if idhit or lc >= WIN:
                hits[loc] = hits.get(loc, 0) + 1
                if lc > best or (idhit and not first):
                    best = max(best, lc)
                    pos = s.find(rid) if idhit else next(s.find(sent[i:i + WIN]) for i in range(len(sent) - WIN + 1)
                                                         if sent[i:i + WIN] in s)
                    first = f"{loc}: ...{s[max(0, pos - 40):pos + 160]}..."
    return dict(item_id=o["item_id"], trace=o["trace"], removed_id=rid, flagged=bool(hits),
                hit_locations=";".join(f"{k}={v}" for k, v in sorted(hits.items())),
                longest_common_substring=best, id_present=id_present,
                first_hit=first.replace("\n", " "), removed_sentence=sent, reading=READING.get(o["item_id"], ""))


def main():
    t = pd.DataFrame([scan_item(o) for o in omission_items()])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT, index=False)
    h = hashlib.sha256(OUT.read_bytes()).hexdigest()
    OUT.with_suffix(".sha256").write_text(f"{h}  {OUT.relative_to(ROOT)}\n")
    f = t[t.flagged]
    print(f"{len(t)} items, flagged {len(f)}: {list(f.item_id)}; sha256 {h}")
    for r in f.itertuples():
        print(r.item_id, r.hit_locations, r.longest_common_substring, r.id_present)


if __name__ == "__main__":
    main()
