"""A13 (D36): launcher job list, R5 filler table, builder sanity, and the analysis on SYNTHETIC call lines
(labelled synthetic; no real outcome is used)."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

from scripts.a13 import launch_ladder as L
from scripts.analysis import a13_addendum as A
from scripts.analysis.a06_addendum import OMISSION_DIR, cluster_meta
from src.analysis.primary import _y
from src.analysis.stats import holm
from src.replay.r5 import build_r5, filler_text
from src.replay.r5_a13 import lookup, omission_items
from src.replay.variants import R4N_SYSTEM_PROMPT, _is_comm_opening, build, load_item
from src.runner.jobs import original_bob_message

ITEMS = omission_items()


# ---------------------------------------------------------------- job list

def test_job_list_800_16_per_item_adjacent_seeded():
    js = L.jobs()
    assert len(js) == 800
    assert len({j.call_id("a13") for j in js}) == 800
    assert all(j.call_id("a13").startswith("a13:LADDER:") for j in js)
    by_item = pd.Series([j.item_id for j in js])
    assert by_item.value_counts().eq(16).all() and by_item.nunique() == 50
    # adjacency: each item's calls form one contiguous block
    blocks = [k for k, _ in __import__("itertools").groupby(by_item)]
    assert len(blocks) == 50
    # seed: item order and within-item order reproduce numpy default_rng(2026)
    rng = np.random.default_rng(2026)
    exp = []
    for i in rng.permutation(len(ITEMS)):
        cells = [(ITEMS[i]["item_id"],) + c for c in L.CELLS]
        exp += [cells[k] for k in rng.permutation(len(cells))]
    assert [(j.item_id, j.variant, j.version, j.draw) for j in js] == exp
    cnt = pd.Series([(j.variant, j.version) for j in js]).value_counts()
    assert len(cnt) == 8 and cnt.eq(100).all()
    assert {j.variant for j in js} == {"R2", "R3", "R4n", "R5"}
    assert all(j.model == "gemini/gemini-3.1-flash-lite" and j.verdict_fn is not None for j in js)
    first = L.first_jobs()
    assert len(first) == 48 and [j.call_id("a13") for j in first] == [j.call_id("a13") for j in js[:48]]


def test_r5_fillers_for_100_item_versions():
    have = lookup()
    assert len(have) == 100, f"missing: {L.missing_fillers()}"
    assert L.missing_fillers() == []
    a13 = pd.read_csv(A.OMISSION_DIR.parents[0] / "r5_fillers_a13.csv")
    assert a13.within_tolerance.all() and (a13.rel_error.abs() <= 0.02).all()
    assert (a13.version == "omission").sum() == 50 and (a13.version == "correct").sum() == 28
    prereg = pd.read_csv(A.OMISSION_DIR.parents[0] / "r5_fillers.csv")
    reused = prereg[(prereg.version == "correct") & prereg.item_id.isin([o["item_id"] for o in ITEMS])]
    assert len(reused) == 22
    assert set(reused.item_id).isdisjoint(set(a13[a13.version == "correct"].item_id))


# ---------------------------------------------------------------- builders

@pytest.mark.parametrize("o", ITEMS[:5], ids=[o["item_id"] for o in ITEMS[:5]])
def test_builder_sanity(o):
    ctx = load_item(o["trace"], int(o["ep_index"]))
    m = ctx.messages
    for version in ("omission", "correct"):
        bob = o["bob_r1_content"] if version == "omission" else m[ctx.cut_idx]["content"]
        r2 = L.build_messages(o, "R2", version)
        # R2: system prompt + current episode up to the cut + verdict prompt; no earlier-episode turn
        exp = [m[0]] + copy.deepcopy(m[ctx.ep_start:ctx.cut_idx]) + [dict(m[ctx.cut_idx], content=bob)] + [m[ctx.verdict_prompt_idx]]
        assert r2 == exp
        assert sum(_is_comm_opening(x) for x in r2) == 1
        # R3: none of the earlier communication phases; everything else of the cut context kept
        r3 = L.build_messages(o, "R3", version)
        drop = set()
        for k in range(ctx.ep_index):
            drop.update(range(ctx.comm_opening_idx(k), ctx.verdict_prompt_of(k)))
        assert drop
        cut = copy.deepcopy(m[:ctx.cut_idx]) + [dict(m[ctx.cut_idx], content=bob)]
        assert r3 == [x for i, x in enumerate(cut) if i not in drop] + [m[ctx.verdict_prompt_idx]]
        assert sum(_is_comm_opening(x) for x in r3) == 1
        assert not any(str(x.get("content")).startswith("[round=") and "[from=bob]" in str(x.get("content"))
                       for x in r3[:-2])
        # R4n: fixed neutral system prompt, then R4's other messages
        r4 = build(ctx, "R4", bob_r1_content=o["bob_r1_content"] if version == "omission" else None)
        r4n = L.build_messages(o, "R4n", version)
        assert r4n[0] == {"role": "system", "content": R4N_SYSTEM_PROMPT} and r4n[1:] == r4[1:]
        # R5 = R4 plus one filler user message before the communication opening
        r5 = L.build_messages(o, "R5", version)
        n = lookup()[(o["item_id"], version)]
        assert r5 == [r4[0], {"role": "user", "content": filler_text(n)}] + r4[1:]
        assert r5 == build_r5(ctx, n, bob_r1_content=o["bob_r1_content"] if version == "omission" else None)


def test_omission_content_in_every_omission_cell():
    for o in ITEMS:
        orig = original_bob_message(o["trace"], int(o["ep_index"]))[0]
        assert orig != o["bob_r1_content"]
        for v in L.VARIANTS:
            om = L.build_messages(o, v, "omission")
            co = L.build_messages(o, v, "correct")
            assert sum(x.get("content") == o["bob_r1_content"] for x in om) == 1, (o["item_id"], v)
            assert not any(x.get("content") == orig for x in om)
            assert sum(x.get("content") == orig for x in co) == 1 and not any(x.get("content") == o["bob_r1_content"] for x in co)
            assert om[-1]["content"].startswith("## Episode ") and "verdict phase" in om[-1]["content"].split("\n")[0]


# ---------------------------------------------------------------- analysis (synthetic)

def _frame(rows):
    f = pd.DataFrame(rows)
    f["y"] = [_y(v, "ok" if v else "missing_error") for v in f.verdict]
    f["reasoning"] = f.get("reasoning", "synthetic")
    return f


def _synthetic(n_items=20):
    """SYNTHETIC: R1-om accepts; R2-om, R4-om, R5-om reject; R3-om = R1; R4n-om rejects on odd items only;
    every correct cell accepts; one R2 omission draw missing (item 0, draw 1)."""
    om = sorted(p.stem for p in OMISSION_DIR.glob("rep*_alice.json"))[:n_items]
    rid = {i: json.loads((OMISSION_DIR / f"{i}.json").read_text())["removed_id"] for i in om}
    new, base = [], []
    verdict_om = {"R1": lambda i: "accept", "R2": lambda i: "reject", "R3": lambda i: "accept",
                  "R4": lambda i: "reject", "R5": lambda i: "reject", "R4n": lambda i: "reject" if i % 2 else "accept"}
    for i, item in enumerate(om):
        for d in (1, 2):
            for v in ("R2", "R3", "R4n", "R5"):
                vd = None if (v == "R2" and i == 0 and d == 1) else verdict_om[v](i)
                new.append(dict(call_id=f"a13:LADDER:{item}:{v}:omission:{d}", item_id=item, variant=v,
                                version="omission", draw=d, verdict=vd, reasoning=f"missing {rid[item]}"))
                new.append(dict(call_id=f"a13:LADDER:{item}:{v}:correct:{d}", item_id=item, variant=v,
                                version="correct", draw=d, verdict="accept"))
            for v in ("R1", "R4"):
                base.append(dict(call_id=f"a06:OMIT:{item}:{v}:omission:{d}", item_id=item, variant=v,
                                 version="omission", draw=d, verdict=verdict_om[v](i), check="OMIT"))
            for v in ("R0p", "R4"):
                base.append(dict(call_id=f"x:{item}:{v}:correct:{d}", item_id=item, variant=v, version="correct",
                                 draw=d, verdict="accept", check="OMIT"))
    return _frame(new), _frame(base), om


def test_synthetic_primary_family_holm_gatekeeping_equivalence():
    new, base, om = _synthetic()
    res = A.analyze_frames(new, base, cluster_meta(), A.items_info())
    P = res["primary"]
    assert list(A.PRIMARY) == ["R2_minus_R1", "R3_minus_R1", "R4_minus_R2", "R5_minus_R4", "R4n_minus_R4"]
    assert P["R2_minus_R1"]["estimate"] == pytest.approx(1.0) and P["R2_minus_R1"]["n_items"] == 20
    assert P["R3_minus_R1"]["estimate"] == 0 and P["R4_minus_R2"]["estimate"] == 0
    assert P["R5_minus_R4"]["estimate"] == 0
    assert P["R4n_minus_R4"]["estimate"] == pytest.approx(-0.5)
    # Holm over exactly the five raw p-values
    raw = {k: P[k]["p"] for k in A.PRIMARY}
    adj = holm(raw)
    assert all(P[k]["p_holm"] == pytest.approx(adj[k]) for k in A.PRIMARY)
    assert P["R2_minus_R1"]["p_holm"] == pytest.approx(min(1.0, 5 * raw["R2_minus_R1"]))
    assert P["R2_minus_R1"]["significant"] and P["R4n_minus_R4"]["significant"]
    assert not P["R3_minus_R1"]["significant"] and not P["R5_minus_R4"]["significant"]
    # gatekeeping: D tested only for significant contrasts; R1's correct counterpart is R0'
    assert P["D_R2_minus_R1"]["tested"] and P["D_R2_minus_R1"]["estimate"] == pytest.approx(1.0)
    assert "R0p" in P["D_R2_minus_R1"]["definition"]
    assert P["D_R4n_minus_R4"]["tested"] and P["D_R4n_minus_R4"]["estimate"] == pytest.approx(-0.5)
    for k in ("R3_minus_R1", "R4_minus_R2", "R5_minus_R4"):
        assert P[f"D_{k}"]["tested"] is False and "p" not in P[f"D_{k}"]
    # equivalence flags
    E = res["equivalence"]
    assert E["R5_minus_R4"]["ci_inside_margin"] is True and E["R5_minus_R4"]["explanation_rejected"] is True
    assert E["R2_minus_R1"]["explanation_rejected"] is False
    # missing verdict: excluded (item 0's R2 cell = its one draw), coded ACCEPT lowers R2 on item 0 to 0.5
    assert res["missing"] == 1
    assert res["primary_missing_as_accept"]["R2_minus_R1"]["estimate"] == pytest.approx(1 - 0.5 / 20)
    assert res["primary_missing_as_reject"]["R2_minus_R1"]["estimate"] == pytest.approx(1.0)
    # descriptive
    V = res["per_variant"]
    assert V["R1"]["detection"]["estimate"] == 0 and V["R2"]["detection"]["estimate"] == 1
    assert V["R2"]["false_rejection"]["estimate"] == 0 and V["R2"]["discrimination"] == pytest.approx(1.0)
    assert V["R2"]["right_reason_deterministic"]["share"] == 1.0
    assert sum(r["items"] for r in V["R5"]["by_episode"]) == 20
    assert res["draw_agreement"]["R4n|omission"]["agreement"] == 1.0
    assert res["calls"] == 320 and res["calls_by_variant_version"]["R5|omission"] == 40
