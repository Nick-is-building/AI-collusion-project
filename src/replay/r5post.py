"""R5-post distance control (D26, assignment A06).

Items: the 40 R1-live items (data/derived/prereg/r1live_subset.csv), bait version.
Context: the R1 context (cut after Bob's round-1 message, bait content) with one user message of
neutral Gutenberg filler (the R5 text, `src.replay.r5.filler_text`: Darwin, eBook #1228, SHA-256
pinned) inserted between Bob's round-1 message and the verdict prompt:
  [... R1 context up to Bob's round-1 message, filler, verdict prompt]
Token matching (+-2%): target T = count(R0, correct) - count(R0', correct), i.e. the tokens of the
original rounds 2-5 of that episode (everything between Bob's round-1 message and the verdict prompt in
the original context). R5-post must satisfy |count(R5-post) - count(R1) - T| <= 0.02 T, with count =
countTokens of the full generateContent request (free endpoint; purpose "r5post_filler"). Search as in
R5 (`src.replay.r5.match_item`): start from the filler's characters per token, then secant steps, at
most MAX_STEPS counts; the first n inside the band is used. Results: data/derived/r5post_fillers.csv,
fixed before any R5-post call.

  PYTHONPATH=. .venv/bin/python -m src.replay.r5post [--live]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.replay.r5 import MAX_STEPS, TOLERANCE, filler_text
from src.replay.request import messages_hash
from src.replay.token_count import count_tokens, http_body, request_kwargs
from src.replay.variants import build, load_item

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "r5post_fillers.csv"
PURPOSE = "r5post_filler"


def build_r5post(ctx, n_chars: int, bob_r1_content: str) -> list[dict]:
    cut = build(ctx, "CUT", bob_r1_content=bob_r1_content)
    return cut[:-1] + [{"role": "user", "content": filler_text(n_chars)}] + cut[-1:]


def _count(messages, task_type, label, live):
    url, body = http_body(request_kwargs(messages, task_type))
    return count_tokens(body, url, purpose=PURPOSE, label=label, live=live)


def match_item(trace: str, ep_index: int, task_type: str, item_id: str, bait_content: str, live: bool) -> dict:
    ctx = load_item(trace, ep_index)
    lab = f"r5post:{item_id}"
    c_r0 = _count(build(ctx, "R0"), task_type, lab + ":R0", live)
    c_cut = _count(build(ctx, "CUT"), task_type, lab + ":R0p", live)
    c_r1 = _count(build(ctx, "CUT", bob_r1_content=bait_content), task_type, lab + ":R1", live)
    target = c_r0 - c_cut
    probe = 20000
    cpt = len(filler_text(probe)) / (_count(build_r5post(ctx, probe, bait_content), task_type, lab + ":probe", live) - c_r1)
    n, tries = int(target * cpt), []
    for _ in range(MAX_STEPS):
        got = _count(build_r5post(ctx, n, bait_content), task_type, lab + f":n{n}", live) - c_r1
        tries.append((n, got))
        if abs(got - target) <= TOLERANCE * target:
            break
        n = max(1000, int(n * target / got))
    n_best, got_best = min(tries, key=lambda x: abs(x[1] - target))
    return dict(item_id=item_id, target_tokens=target, filler_tokens=got_best, rel_error=(got_best - target) / target,
                within_tolerance=abs(got_best - target) <= TOLERANCE * target, n_chars=n_best,
                filler_chars=len(filler_text(n_best)), count_R0=c_r0, count_R0p=c_cut, count_R1=c_r1,
                count_R5post=c_r1 + got_best, n_count_calls=4 + len(tries),
                messages_sha256=messages_hash(build_r5post(ctx, n_best, bait_content)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="countTokens calls for counts not yet cached (free)")
    a = ap.parse_args(argv)
    from src.runner.item_lists import load_bait_content, main_items, r1live_subset
    m = main_items().set_index("item_id").loc[r1live_subset()].reset_index()
    rows = pd.read_csv(OUT).to_dict("records") if OUT.exists() else []
    done = {r["item_id"] for r in rows}
    for r in m.itertuples():
        if r.item_id in done:
            continue
        res = match_item(r.trace, int(r.ep_index), r.task_type, r.item_id, load_bait_content(r.item_id), a.live)
        rows.append(res)
        pd.DataFrame(rows).sort_values("item_id").to_csv(OUT, index=False)
        print(res["item_id"], res["target_tokens"], res["filler_tokens"], f"{res['rel_error']:+.4f}", res["within_tolerance"], flush=True)
    d = pd.DataFrame(rows)
    print(f"R5-post fillers: {len(d)} rows, within ±2%: {int(d.within_tolerance.sum())}")


if __name__ == "__main__":
    main()
