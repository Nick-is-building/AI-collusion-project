"""R1-live screen and analysis (D19), on clearly synthetic call lines."""
import numpy as np
import pandas as pd

from src.analysis.r1live import analyze_r1live, live_frame
from src.replay.r1live_screen import markers, original_answer, screen
from src.runner.item_lists import load_bait

SUBSET = pd.read_csv("data/derived/prereg/r1live_subset.csv").item_id.tolist()
EX, DS = "rep005_e06_alice", "rep001_e04_alice"


def line(item, verdict, msgs):   # synthetic runner call line
    return {"call_id": f"x:{item}", "item_id": item, "variant": "R1live", "version": "bait", "draw": 1,
            "verdict": verdict, "verdict_status": "ok", "extra": {"r1live": {"live_messages": msgs, "signature_mode": "keep"}}}


def test_screen_flags_and_reaction():
    b = load_bait(EX)
    orig = " ".join(original_answer(b))
    msgs = [{"round": 2, "from": "alice", "content": f"You included {b['bait_id']}, which should be excluded."},
            {"round": 2, "from": "bob", "content": "You are right, good catch. My answer was " + orig},
            {"round": 3, "from": "bob", "content": "I did not include that record."}]
    s = screen(line(EX, "reject", msgs), b)
    assert s["alice_names_bait"] and s["alice_names_bait_round"] == 2
    assert s["bob_reaction_keyword"] == "concede"
    assert s["flag_a"] and s["flag_a_rounds"] == [2]
    assert s["flag_b_candidates"][0]["round"] == 3
    s2 = screen(line(EX, "accept", [{"round": 2, "from": "alice", "content": "Looks good."}]), b)
    assert not s2["alice_names_bait"] and s2["bob_reaction_keyword"] is None and not s2["flag_a"]


def test_data_search_relaxed_literal_marker():
    b = load_bait(DS)
    assert str(b["added_value"]).strip("'") in markers(b)


def test_analysis_runs_on_synthetic():
    baits = {i: load_bait(i) for i in SUBSET}
    rng = np.random.default_rng(1)
    recs = [line(i, "reject" if rng.random() < 0.6 else "accept", [{"round": 2, "from": "alice", "content": "ok"}])
            for i in SUBSET]
    live = live_frame(recs, baits)
    main = pd.DataFrame([dict(item_id=i, variant="R1", version="bait", draw=d, y=float(rng.random() < 0.9))
                         for i in SUBSET for d in (1, 2)])
    cand = pd.read_csv("data/derived/items/candidates.csv")
    meta = cand.set_index("item_id").assign(cluster=lambda m: m.trace)
    r = analyze_r1live(main, live, meta, SUBSET, cand, confirmed_flag_b={SUBSET[0]}, confirmed_reaction={},
                       n_draws=500)
    assert r["primary"]["n_items"] == 40 and r["without_flags"]["n_items"] == 39
    assert r["flags"]["flagged"] == 1 and not r["flags"]["limited_ecological_check"]
    assert r["composition"]["trajectories"] == cand.set_index("item_id").loc[SUBSET].trace.nunique()
    assert abs(r["primary"]["estimate"] - (live.y.mean() - main.groupby("item_id").y.mean().mean())) < 1e-9
    assert set(r["decision"]) == {"erodes", "rescues"}
