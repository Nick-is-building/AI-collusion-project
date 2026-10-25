"""A10 task 6 (EXPLORATORY, zero cost, no new call): recognise-and-approve table over the existing variants.

For every planted-error call that ended in ACCEPT, is there evidence that the verifier recognised the planted
error? Three separate channels, never pooled:
  (1) reasoning text: the verdict's reasoning contains a deterministic marker of the planted error
      (src.analysis.primary.right_reason). Commission baits: the item's prereg markers (bait record ID, bait
      sentence, relaxed value; src.analysis.meta.main_meta). Omission baits (D25): removed record ID or removed
      sentence. For R6/R6s/R6x the FIRST verdict and its reasoning are used (their primary outcome).
  (2) the verifier's own list: R6s (D28) first `source_items` contains the removed sentence
      (a07_addendum._listed_removed); R6x (D30) first `source_classification` labels the removed sentence
      include (r6x.label_of). Reported for accepts (and rejects for reference).
  (3) Alice's live messages in R1-live: the deterministic screen's `alice_names_bait`
      (src.replay.r1live_screen), crossed with the final verdict.
Per row: accepts, "named and accepted" (marker present), "not named and accepted"; rejects for reference.
Caveats: markers are lexical (they miss paraphrases and partial quotes, and a marker can appear when the
verifier names the record but endorses it); reasoning is a public self-report and hidden thinking is not
stored, so "not named" is not evidence of non-recognition. Natural errors (N1/N4) have no planted marker
and are not included. A10 cells are included when stage a10 exists.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analysis.a06_addendum import OMISSION_DIR, load_stage
from src.analysis.primary import right_reason
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "results" / "raw"


def _row(source, variant, version_kind, y, named):
    y, named = list(y), list(named)
    acc = [n for v, n in zip(y, named) if v == 0]
    rej = [n for v, n in zip(y, named) if v == 1]
    return dict(source=source, variant=variant, error=version_kind, calls=len(y),
                missing=sum(1 for v in y if v != v), accepts=len(acc), named_accepts=int(sum(acc)),
                not_named_accepts=len(acc) - int(sum(acc)), rejects=len(rej), named_rejects=int(sum(rej)))


def _omission_markers():
    return {p.stem: json.loads(p.read_text()) for p in OMISSION_DIR.glob("rep*_alice.json")}


def reasoning_channel(main_calls: pd.DataFrame, meta: pd.DataFrame) -> list[dict]:
    rows = []
    bait = main_calls[main_calls.version == "bait"]
    for v in ("R1", "R2", "R3", "R4", "R4n", "R5", "R6"):
        s = bait[bait.variant == v]
        if v == "R6":
            y, text = s.r6_first_y, s.first_reasoning
        else:
            y, text = s.y, s.reasoning
        named = [right_reason(t, meta.loc[i, "markers"]) for t, i in zip(text, s.item_id)]
        rows.append(_row("main run", v + (" (first verdict)" if v == "R6" else ""), "commission", y, named))
    for stage, var in (("a06", "R5post"),):
        s = load_stage(stage)
        s = s[(s.variant == var)]
        named = [right_reason(t, meta.loc[i, "markers"]) for t, i in zip(s.reasoning, s.item_id)]
        rows.append(_row(stage, var, "commission", s.y, named))
    live = [r for r in iter_call_lines(RAW) if r.get("stage") == "r1live" and r.get("mode") == "live"]
    from src.analysis.primary import _y
    rows.append(_row("r1live", "R1-live (final verdict reasoning)", "commission",
                     [_y(r.get("verdict"), r.get("verdict_status")) for r in live],
                     [right_reason(r.get("reasoning") or "", meta.loc[r["item_id"], "markers"]) for r in live]))
    om = _omission_markers()

    def om_rows(stage, variant, ycol="y", tcol="reasoning", loader=None, label=None):
        s = loader() if loader else load_stage(stage)
        s = s[(s.variant == variant) & (s.version == "omission")]
        if s.empty:
            return
        named = [right_reason(t, om[i]["right_reason_markers"]) for t, i in zip(s[tcol], s.item_id)]
        rows.append(_row(stage, label or variant, "omission", s[ycol], named))
    om_rows("a06", "R1")
    om_rows("a06", "R4")
    from scripts.analysis.a07_addendum import load_a07
    from scripts.analysis.a08_addendum import load_a08
    om_rows("a07", "R6s", "r6s_first_y", "first_reasoning_r6s", load_a07, "R6s (first verdict)")
    om_rows("a07", "R6", "r6_first_y", "first_reasoning", load_a07, "R6 (first verdict)")
    om_rows("a08", "R6x", "r6x_first_y", "first_reasoning_r6x", load_a08, "R6x (first verdict)")
    a10 = load_stage("a10")
    if len(a10):
        for v in sorted(a10.variant.unique()):
            om_rows("a10", v, loader=lambda: a10)
    return rows


def list_channel() -> list[dict]:
    from scripts.analysis.a07_addendum import _listed_removed, load_a07
    from scripts.analysis.a08_addendum import load_a08
    from src.replay.r6x import label_of
    om = _omission_markers()
    rows = []
    a07 = load_a07()
    s = a07[(a07.variant == "R6s") & (a07.version == "omission")]
    listed = [_listed_removed(js, om[i]["removed_sentence"]) for js, i in zip(s.r6s_first_items, s.item_id)]
    rows.append(dict(_row("a07", "R6s (first verdict; removed sentence listed in source_items)", "omission",
                          s.r6s_first_y, [bool(x) for x in listed])))
    a08 = load_a08()
    s = a08[(a08.variant == "R6x") & (a08.version == "omission")]
    lab = [label_of(json.loads(js), om[i]["removed_sentence"]) for js, i in zip(s.r6x_first_classification, s.item_id)]
    rows.append(dict(_row("a08", "R6x (first verdict; removed sentence labeled include)", "omission",
                          s.r6x_first_y, [x == "include" for x in lab]),
                     labels_of_accepts=pd.Series([x for x, y in zip(lab, s.r6x_first_y) if y == 0],
                                                 dtype=object).value_counts().to_dict()))
    return rows


def live_channel() -> list[dict]:
    from src.analysis.primary import _y
    from src.replay.r1live_screen import screen
    from src.runner.item_lists import load_bait
    live = [r for r in iter_call_lines(RAW) if r.get("stage") == "r1live" and r.get("mode") == "live"]
    named = [bool(screen(r, load_bait(r["item_id"]))["alice_names_bait"]) for r in live]
    return [_row("r1live", "R1-live (Alice names the bait in her live messages; final verdict)", "commission",
                 [_y(r.get("verdict"), r.get("verdict_status")) for r in live], named)]


def build(main_calls: pd.DataFrame, meta: pd.DataFrame) -> dict:
    return {"label": "EXPLORATORY (A10 task 6): recognise-and-approve, three separate channels; zero cost",
            "caveats": __doc__.split("Caveats: ", 1)[1].strip(),
            "reasoning_text": reasoning_channel(main_calls, meta),
            "verifier_list": list_channel(),
            "r1live_messages": live_channel()}
