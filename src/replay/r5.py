"""R5: R4 plus a token-matched neutral filler (PROJECT_PLAN.md section 8.4; assignment A03 task 3).

Filler source: Charles Darwin, *On the Origin of Species* (1st edition), Project Gutenberg eBook #1228,
downloaded by `python -m src.replay.r5 --download` from FILLER_URL into data/raw/filler/pg1228.txt
(git-ignored; SHA-256 pinned in FILLER_SHA256 and checked on every load).

Filler text: the body from the "INTRODUCTION." heading that opens the main text (the second one; the
first two belong to the table of contents) to the Gutenberg end marker. Hard line wraps inside a
paragraph are joined with single spaces; paragraphs are separated by one blank line. The filler of
length n is the first n characters of that body, cut back to the last whitespace (so no word is split).

R5 message list: [system prompt, filler (one user message), communication opening of the current
episode, Bob's round-1 message, verdict prompt], i.e. R4 with the filler inserted as one user message
before the communication opening (plan 8.4).

Token matching (A03; countTokens is free and authorized for this purpose):
  target T = count(R1 request) - count(R4 request) on the bait version, and
             count(R0' request) - count(R4 request) on the correct version,
  where count = countTokens of the full generateContent request LiteLLM would send (system
  instruction, contents, verdict tool, tool config). R5 must satisfy
  |count(R5 request) - count(R4 request) - T| <= 0.02 * T.
  Search: start at n = T x (characters per token of the filler, measured once on a 20,000-character
  prefix), then n <- n x T / achieved (secant steps), at most MAX_STEPS countTokens calls per item and
  version. The first n inside the band is used. Results (n_chars, tokens, target, all counts) are
  written to data/derived/r5_fillers.csv, which fixes the R5 stimuli before the main run.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.replay.token_count import count_tokens, http_body, request_kwargs
from src.replay.variants import build, load_item

ROOT = Path(__file__).resolve().parents[2]
FILLER_URL = "https://www.gutenberg.org/cache/epub/1228/pg1228.txt"
FILLER_PATH = ROOT / "data" / "raw" / "filler" / "pg1228.txt"
FILLER_SHA256 = "362142cb7c6f90850477520cfe2a62fe423ae92ea8eb6d9cd8b30ddb39de60b9"
OUT = ROOT / "data" / "derived" / "r5_fillers.csv"
TOLERANCE = 0.02
MAX_STEPS = 8


def download():
    import httpx
    FILLER_PATH.parent.mkdir(parents=True, exist_ok=True)
    r = httpx.get(FILLER_URL, follow_redirects=True, timeout=60)
    r.raise_for_status()
    FILLER_PATH.write_bytes(r.content)
    return hashlib.sha256(r.content).hexdigest()


@lru_cache(maxsize=1)
def filler_body() -> str:
    data = FILLER_PATH.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    if h != FILLER_SHA256:
        raise RuntimeError(f"filler checksum mismatch: {h}")
    text = data.decode("utf-8").replace("\r\n", "\n")
    end = text.index("*** END OF THE PROJECT GUTENBERG EBOOK")
    starts = [m.start() for m in re.finditer(r"^INTRODUCTION\.$", text, re.M)]
    body = text[starts[1]:end]
    paras = [" ".join(line.strip() for line in p.splitlines() if line.strip()) for p in re.split(r"\n\s*\n", body)]
    return "\n\n".join(p for p in paras if p)


def filler_text(n_chars: int) -> str:
    body = filler_body()
    if n_chars >= len(body):
        raise ValueError(f"filler of {n_chars} characters exceeds the text ({len(body)})")
    cut = body[:n_chars]
    i = max(cut.rfind(" "), cut.rfind("\n"))
    return cut[:i].rstrip() if i > 0 else cut


def build_r5(ctx, n_chars: int, bob_r1_content: str | None = None) -> list[dict]:
    r4 = build(ctx, "R4", bob_r1_content=bob_r1_content)
    return [r4[0], {"role": "user", "content": filler_text(n_chars)}] + r4[1:]


def _count(messages, task_type, label, live):
    url, body = http_body(request_kwargs(messages, task_type))
    return count_tokens(body, url, purpose="r5_filler", label=label, live=live)


def match_item(trace: str, ep_index: int, task_type: str, item_id: str, version: str,
               bob_r1_content: str | None, live: bool) -> dict:
    ctx = load_item(trace, ep_index)
    lab = f"r5:{item_id}:{version}"
    big = build(ctx, "CUT", bob_r1_content=bob_r1_content)        # R1 (bait) or R0' (correct)
    r4 = build(ctx, "R4", bob_r1_content=bob_r1_content)
    c_big, c_r4 = _count(big, task_type, lab + ":R1orR0p", live), _count(r4, task_type, lab + ":R4", live)
    target = c_big - c_r4
    probe = 20000
    c_probe = _count(build_r5(ctx, probe, bob_r1_content), task_type, lab + ":probe", live) - c_r4
    cpt = len(filler_text(probe)) / c_probe
    n = int(target * cpt)
    tries = []
    for _ in range(MAX_STEPS):
        got = _count(build_r5(ctx, n, bob_r1_content), task_type, lab + f":n{n}", live) - c_r4
        tries.append((n, got))
        if abs(got - target) <= TOLERANCE * target:
            break
        n = max(1000, int(n * target / got))
    n_best, got_best = min(tries, key=lambda x: abs(x[1] - target))
    ok = abs(got_best - target) <= TOLERANCE * target
    msgs = build_r5(ctx, n_best, bob_r1_content)
    from src.replay.request import messages_hash
    return dict(item_id=item_id, version=version, target_tokens=target, filler_tokens=got_best,
                rel_error=(got_best - target) / target, within_tolerance=ok, n_chars=n_best,
                filler_chars=len(filler_text(n_best)), count_R1_or_R0p=c_big, count_R4=c_r4,
                count_R5=c_r4 + got_best, n_count_calls=3 + len(tries), messages_sha256=messages_hash(msgs))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--items", default="main+p5", help="main, p5, main+p5")
    ap.add_argument("--live", action="store_true", help="countTokens calls for counts not yet cached")
    a = ap.parse_args(argv)
    if a.download:
        print("downloaded, sha256", download())
        return
    from src.runner.item_lists import main_items, p5_items, load_bait_content
    rows = []
    items = []
    if "main" in a.items:
        items += list(main_items().itertuples())
    if "p5" in a.items:
        items += list(p5_items().itertuples())
    done = set()
    if OUT.exists():
        prev = pd.read_csv(OUT)
        rows = prev.to_dict("records")
        done = {(r["item_id"], r["version"]) for r in rows}
    for r in items:
        for version in ("bait", "correct"):
            if (r.item_id, version) in done:
                continue
            b = load_bait_content(r.item_id) if version == "bait" else None
            res = match_item(r.trace, int(r.ep_index), r.task_type, r.item_id, version, b, a.live)
            rows.append(res)
            done.add((r.item_id, version))
            pd.DataFrame(rows).sort_values(["item_id", "version"]).to_csv(OUT, index=False)
            print(res["item_id"], version, res["target_tokens"], res["filler_tokens"], f"{res['rel_error']:+.4f}",
                  res["within_tolerance"], flush=True)
    d = pd.DataFrame(rows)
    print(f"R5 fillers: {len(d)} rows, within ±2%: {int(d.within_tolerance.sum())}")


if __name__ == "__main__":
    main()
