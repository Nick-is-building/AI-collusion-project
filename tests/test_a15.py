"""A15 (D38): R3t / R3o builders, launcher job list, and the analysis on SYNTHETIC call lines (labelled synthetic;
no real outcome is used)."""
import hashlib
import itertools
import json

import numpy as np
import pandas as pd
import pytest

from scripts.a15 import launch_a15 as L
from scripts.analysis import a15_addendum as A
from scripts.analysis.a06_addendum import OMISSION_DIR, cluster_meta
from scripts.analysis.a13_addendum import items_info
from src.analysis.primary import _y
from src.analysis.stats import holm
from src.replay import r3_history as H
from src.replay.request import canonical_json
from src.replay.r5_a13 import omission_items
from src.replay.variants import build, load_item

ITEMS = omission_items()


def _h(m):
    return hashlib.sha256(canonical_json(m).encode()).hexdigest()


def _is_subsequence(sub, seq):
    it = iter(seq)
    return all(x in it for x in sub)


@pytest.mark.parametrize("o", ITEMS, ids=[o["item_id"] for o in ITEMS])
def test_r3t_r3o_structure(o):
    ctx = load_item(o["trace"], int(o["ep_index"]))
    m = ctx.messages
    assert H.split_problems(ctx) == []
    versions = ("omission", "correct") if o is ITEMS[0] or o["item_id"] < "rep010" else ("omission",)
    for version in versions:
        content = o["bob_r1_content"] if version == "omission" else None
        r1, r3 = build(ctx, "CUT", content), build(ctx, "R3", content)
        h3 = [_h(x) for x in r3]
        n_cur = ctx.cut_idx - ctx.ep_start + 2          # current episode up to Bob's message, plus the verdict prompt
        for v, removed_seg in (("R3t", "outcome"), ("R3o", "task")):
            out = H.build(ctx, v, content)
            ho = [_h(x) for x in out]
            # kept messages byte-identical to R3, in R3's order
            assert _is_subsequence(ho, h3)
            # exactly the variant's earlier segments are removed from R3
            exp_removed = sum(e - s for s, e in (H.segments(ctx, k)[removed_seg] for k in range(ctx.ep_index)))
            assert len(r3) - len(out) == exp_removed > 0
            # system prompt kept; current episode byte-identical to R1
            assert ho[0] == _h(m[0])
            assert ho[-n_cur:] == [_h(x) for x in r1[-n_cur:]]
            assert out[-2]["content"] == (content if content is not None else m[ctx.cut_idx]["content"])
            texts = [str(x.get("content") or "") for x in out[:-n_cur]]
            ids = {t["id"] for x in out for t in (x.get("tool_calls") or [])}
            for k in range(ctx.ep_index):
                seg = H.segments(ctx, k)
                rem_ids = {t["id"] for x in m[slice(*seg[removed_seg])] for t in (x.get("tool_calls") or [])}
                assert rem_ids and not (rem_ids & ids)            # removed segment absent
                comm_ids = {t["id"] for x in m[slice(*seg["comm"])] for t in (x.get("tool_calls") or [])}
                assert not (comm_ids & ids)                       # communication absent (as in R3)
                if v == "R3t":
                    assert not any(t.startswith(f"Episode {k + 1} complete") or t.startswith(f"## Episode {k + 1}: verdict phase")
                                   for t in texts)
                    assert any(t.startswith(f"## Episode {k + 1}: task phase") for t in texts)
                else:
                    assert not any(t.startswith(f"## Episode {k + 1}: task phase") for t in texts)
                    assert any(t.startswith(f"Episode {k + 1} complete") for t in texts)
            # tool calls and results stay paired
            res = {x["tool_call_id"] for x in out if x["role"] == "tool"}
            assert ids == res


def test_job_list_400_8_per_item_adjacent_seeded():
    js = L.jobs()
    assert len(js) == 400 and len({j.call_id("a15") for j in js}) == 400
    assert all(j.call_id("a15").startswith("a15:HIST:") for j in js)
    s = pd.Series([j.item_id for j in js])
    assert s.nunique() == 50 and s.value_counts().eq(8).all()
    assert len([k for k, _ in itertools.groupby(s)]) == 50
    rng = np.random.default_rng(2026)
    exp = []
    for i in rng.permutation(len(ITEMS)):
        cells = [(ITEMS[i]["item_id"],) + c for c in L.CELLS]
        exp += [cells[k] for k in rng.permutation(len(cells))]
    assert [(j.item_id, j.variant, j.version, j.draw) for j in js] == exp
    assert pd.Series([(j.variant, j.version) for j in js]).value_counts().eq(100).all()
    first = L.first_jobs()
    assert len(first) == 24 and [j.call_id("a15") for j in first] == [j.call_id("a15") for j in js[:24]]
    assert all(j.verdict_fn is not None and j.model == "gemini/gemini-3.1-flash-lite" for j in js)


def _frame(rows):
    f = pd.DataFrame(rows)
    f["y"] = [_y(v, "ok" if v else "missing_error") for v in f.verdict]
    if "reasoning" not in f:
        f["reasoning"] = "synthetic"
    f["reasoning"] = f.reasoning.fillna("synthetic")
    return f


def _synthetic(n_items=20):
    """SYNTHETIC: R1 and R3 accept the omission; R3t rejects it; R3o rejects on odd items; R2 rejects; every correct
    cell accepts except R3t correct on item 1 (one false rejection); one R3o omission draw missing (item 0, draw 1)."""
    om = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))[:n_items]
    rid = {i: json.loads((OMISSION_DIR / f"{i}.json").read_text())["removed_id"] for i in om}
    new, base = [], []
    vo = {"R1": lambda i: "accept", "R3": lambda i: "accept", "R2": lambda i: "reject",
          "R3t": lambda i: "reject", "R3o": lambda i: "reject" if i % 2 else "accept"}
    for i, item in enumerate(om):
        for d in (1, 2):
            for v in ("R3t", "R3o"):
                vd = None if (v == "R3o" and i == 0 and d == 1) else vo[v](i)
                new.append(dict(call_id=f"a15:HIST:{item}:{v}:omission:{d}", item_id=item, variant=v, version="omission",
                                draw=d, verdict=vd, reasoning=f"missing {rid[item]}" if vd == "reject" else "complete"))
                new.append(dict(call_id=f"a15:HIST:{item}:{v}:correct:{d}", item_id=item, variant=v, version="correct",
                                draw=d, verdict="reject" if (v == "R3t" and i == 1) else "accept"))
            for v in ("R1", "R3", "R2"):
                base.append(dict(call_id=f"b:{item}:{v}:omission:{d}", item_id=item, variant=v, version="omission",
                                 draw=d, verdict=vo[v](i)))
            for v in ("R0p", "R3", "R2"):
                base.append(dict(call_id=f"b:{item}:{v}:correct:{d}", item_id=item, variant=v, version="correct",
                                 draw=d, verdict="accept"))
    toks = {}
    for r in new + base:
        if r["version"] == "omission":
            toks[r["call_id"]] = {"R1": 1000, "R3": 600, "R3t": 550, "R3o": 200, "R2": 100}[r["variant"]]
    return _frame(new), _frame(base), toks


def test_synthetic_holm_pair_gatekeeping_tokens():
    new, base, toks = _synthetic()
    res = A.analyze_frames(new, base, cluster_meta(), items_info(), toks)
    P = res["primary"]
    assert set(A.PRIMARY) == {"H_out", "H_work"}
    assert P["H_out"]["estimate"] == pytest.approx(1.0)
    assert P["H_work"]["estimate"] == pytest.approx(0.5)     # item 0's R3o cell is its one (accept) draw
    adj = holm({k: P[k]["p"] for k in ("H_out", "H_work")})
    assert all(P[k]["p_holm"] == pytest.approx(adj[k]) for k in ("H_out", "H_work"))
    assert P["H_out"]["p_holm"] == pytest.approx(min(1.0, 2 * min(P["H_out"]["p"], P["H_work"]["p"])))
    assert P["H_out"]["significant"] and P["D_H_out"]["tested"]
    # D_out = [y(R3t,om) - y(R3t,cor)] - [y(R3,om) - y(R3,cor)]: 1 everywhere except item 1 (0)
    assert P["D_H_out"]["estimate"] == pytest.approx(1 - 1 / 20)
    assert "y(R3,correct)" in P["D_H_out"]["definition"]
    assert P["H_out"]["ci_inside_equivalence_margin"] is False
    assert res["missing"] == 1
    assert res["primary_missing_as_reject"]["H_work"]["estimate"] == pytest.approx(0.5 + 0.5 / 20)
    S = res["secondary"]
    assert S["contrasts"]["R3t_minus_R1"]["estimate"] == pytest.approx(1.0)
    assert S["contrasts"]["R3t_minus_R2"]["estimate"] == pytest.approx(0.0)
    assert S["per_variant"]["R3t"]["false_rejection"]["estimate"] == pytest.approx(0.05)
    assert S["per_variant"]["R3o"]["removed_tokens_vs_R1"]["median"] == 800
    pts = {p["variant"]: p for p in S["scatter_detection_vs_removed_tokens"]["points"]}
    assert pts["R1"]["median_removed_tokens"] == 0 and pts["R2"]["median_removed_tokens"] == 900
    assert S["per_variant"]["R3t"]["right_reason_deterministic"] == {"rejects": 40, "right_reason": 40}
    assert S["per_variant"]["R3o"]["named_accept"]["named_accept"] == 0
