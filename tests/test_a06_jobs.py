"""A06 addendum jobs (D25, D26): counts, contexts, R5-post matching table (no API calls)."""
import collections

import pandas as pd

from scripts.a06.launch_addendum import jobs, omission_items
from src.replay.r5post import OUT as R5POST
from src.replay.request import messages_hash
from src.replay.variants import build, load_item
from src.runner.item_lists import load_bait_content, main_items, r1live_subset


def test_job_list():
    js = jobs()
    main_ids = set(main_items().item_id)
    om = omission_items()
    n_out = sum(o["item_id"] not in main_ids for o in om)
    c = collections.Counter((j.check, j.variant, j.version) for j in js)
    assert c[("OMIT", "R1", "omission")] == c[("OMIT", "R4", "omission")] == 2 * len(om)
    assert c[("OMIT", "R0p", "correct")] == c[("OMIT", "R4", "correct")] == 2 * n_out
    assert c[("R5POST", "R5post", "bait")] == 80
    assert len({j.call_id("a06") for j in js}) == len(js)
    assert not {j.item_id for j in js if j.version == "correct"} & main_ids   # reused from the main run


def test_r5post_table_and_context():
    d = pd.read_csv(R5POST)
    assert sorted(d.item_id) == sorted(r1live_subset()) and d.within_tolerance.all()
    assert (d.rel_error.abs() <= 0.02).all()
    js = {j.item_id: j for j in jobs() if j.variant == "R5post"}
    for r in d.head(5).itertuples():
        msgs = js[r.item_id].build_messages()
        assert messages_hash(msgs) == r.messages_sha256
        m = main_items().set_index("item_id").loc[r.item_id]
        r1 = build(load_item(m.trace, int(m.ep_index)), "CUT", bob_r1_content=load_bait_content(r.item_id))
        assert msgs[:-2] == r1[:-1] and msgs[-1] == r1[-1] and msgs[-2]["role"] == "user"
        assert msgs[-3]["content"].startswith("[round=1/5][from=bob]")


def test_omission_jobs_use_omission_content():
    js = [j for j in jobs() if j.check == "OMIT" and j.version == "omission"][:8]
    om = {o["item_id"]: o for o in omission_items()}
    for j in js:
        msgs = j.build_messages()
        assert any(m.get("content") == om[j.item_id]["bob_r1_content"] for m in msgs)
