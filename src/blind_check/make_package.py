"""Blind bait check package for Nick (PROJECT_PLAN.md section 8.3, rule 4; A01 task 7).

Draws N random items with a validated bait (seed SEED, numpy default_rng; draw order: item sample,
then one shuffle per pair) and writes, per pair, one Markdown file with only
  - Bob's task information (the "### Bob's Task information" section of Alice's communication-phase
    prompt), and
  - the transmitted raw log of both versions (pretty-printed JSON, identical formatting),
labelled A and B. Bob's framing text is not shown. The form blind_check/answers_nick.md asks, per
pair, which version is the bait and what the error is.

The answer key goes to blind_check/key.local.json (git-ignored); only its SHA-256 is committed
(blind_check/key_sha256.txt). Refuses to run if fewer than N validated baits exist.

Usage: .venv/bin/python -m src.blind_check.make_package [--n 20] [--out blind_check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

from src.replay.variants import load_item

ROOT = Path(__file__).resolve().parents[2]
BAITS = ROOT / "data" / "derived" / "baits"
SEED = 2026


def task_information(trace: str, ep_index: int) -> str:
    ctx = load_item(trace, ep_index)
    opening = ctx.messages[ctx.comm_opening_idx(ep_index)]["content"]
    m = re.search(r"### Bob's Task information\n\n(.*?)\n\n### ", opening, re.S)
    return m.group(1).strip()


def pretty(raw: str) -> str:
    return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)


def make(n: int, out: Path, seed: int = SEED, baits_dir: Path = BAITS) -> dict:
    recs = [json.loads(p.read_text()) for p in sorted(baits_dir.glob("*.json"))]
    if len(recs) < n:
        raise SystemExit(f"blocked: {len(recs)} validated baits, {n} pairs required")
    rng = np.random.default_rng(seed)
    chosen = [recs[i] for i in sorted(rng.choice(len(recs), size=n, replace=False))]
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    key, form = {"seed": seed, "n": n, "pairs": {}}, ["# Blind bait check — answers (Nick)\n",
        "For each pair: which version (A or B) contains the planted error, and what the error is.\n"]
    for k, rec in enumerate(chosen, 1):
        from src.replay.traces import episode_bounds, get_log_raw, load_trace
        t = load_trace(rec["trace"])
        raw = get_log_raw(t["results"][rec["ep_index"]]["agents"]["bob"]["messages"],
                          *episode_bounds(t, rec["ep_index"], "bob"))
        bait_raw = rec["bait_raw_log"]
        assert bait_raw in rec["bob_r1_content"]
        json.loads(bait_raw)
        bait_is_a = bool(rng.integers(0, 2))
        a, b = (bait_raw, raw) if bait_is_a else (raw, bait_raw)
        pid = f"pair_{k:02d}"
        (out / "pairs" / f"{pid}.md").write_text(
            f"# {pid}\n\n## Task information\n\n{task_information(rec['trace'], rec['ep_index'])}\n\n"
            f"## Version A — transmitted log\n\n```json\n{pretty(a)}\n```\n\n"
            f"## Version B — transmitted log\n\n```json\n{pretty(b)}\n```\n")
        key["pairs"][pid] = {"item_id": rec["item_id"], "bait_version": "A" if bait_is_a else "B",
                             "bait_id": rec["bait_id"], "bait_sentence": rec["bait_sentence"]}
        form.append(f"\n## {pid}\n\n- Bait version (A/B):\n- The error:\n")
    (out / "answers_nick.md").write_text("".join(form))
    key_bytes = json.dumps(key, indent=1, ensure_ascii=False).encode()
    (out / "key.local.json").write_bytes(key_bytes)
    digest = hashlib.sha256(key_bytes).hexdigest()
    (out / "key_sha256.txt").write_text(f"{digest}  key.local.json\n")
    return {"n": n, "key_sha256": digest}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "blind_check"))
    a = ap.parse_args()
    print(make(a.n, Path(a.out)))


if __name__ == "__main__":
    sys.exit(main())
