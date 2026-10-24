"""Job builders for all variants and the main-run list (src/runner/jobs.py); no network."""
import collections

import pandas as pd
import pytest

from src.replay.request import messages_hash
from src.replay.variants import build, load_item
from src.runner.item_lists import load_bait, main_items, natural_error_items, p5_items, r1live_subset
from src.runner.jobs import R5_TABLE, main_run_jobs, make_job


@pytest.fixture(scope="module")
def jobs():
    return main_run_jobs()


def test_main_run_counts_and_ids(jobs):
    n = len(main_items())
    c = collections.Counter((j.variant, j.version) for j in jobs)
    assert c[("R1", "bait")] == c[("R0p", "correct")] == c[("R4", "bait")] == c[("R4", "correct")] == 2 * n
    assert c[("R0", "correct")] == c[("R5", "bait")] == c[("R6", "correct")] == n
    assert c[("N1", "correct")] == c[("N4", "correct")] == len(natural_error_items())
    assert c[("FR0", "correct")] == 3 * 63
    assert len({j.call_id("main") for j in jobs}) == len(jobs) == 19 * n + 70 + 189
    # all calls of a main item are adjacent (plan 8.5)
    seq = [j.item_id for j in jobs if j.variant not in ("N1", "N4", "FR0")]
    blocks = [k for k, _ in __import__("itertools").groupby(seq)]
    assert len(blocks) == len(set(blocks)) == n


def test_r5_messages_reproduce_table_hash():
    t = pd.read_csv(R5_TABLE)
    assert t.within_tolerance.all() and (t.rel_error.abs() <= 0.02).all()
    for r in t.head(12).itertuples():
        row = (main_items().set_index("item_id").reindex([r.item_id]).reset_index()
               if r.item_id in set(main_items().item_id) else p5_items().set_index("item_id").loc[[r.item_id]].reset_index())
        j = make_job("T", next(row.itertuples()), "R5", r.version)
        msgs = j.build_messages()
        assert messages_hash(msgs) == r.messages_sha256
        assert len(msgs) == 5 and msgs[1]["role"] == "user" and msgs[1]["content"].startswith("INTRODUCTION.")


def test_variant_contexts():
    row = next(main_items().itertuples())
    b = load_bait(row.item_id)
    ctx = load_item(row.trace, row.ep_index)
    j1 = make_job("T", row, "R1", "bait")
    assert j1.build_messages() == build(ctx, "CUT", bob_r1_content=b["bob_r1_content"])
    j6 = make_job("T", row, "R6", "correct")
    assert j6.build_messages() == build(ctx, "CUT") and j6.verdict_fn is not None
    with pytest.raises(ValueError):
        make_job("T", row, "R1", "correct")
    with pytest.raises(ValueError):
        make_job("T", row, "R0", "bait")
    nat = next(natural_error_items().itertuples())
    n1, n4 = make_job("T", nat, "N1"), make_job("T", nat, "N4")
    assert n1.build_messages()[-1] == n4.build_messages()[-1]          # same verdict prompt
    assert len(n4.build_messages()) == 4


def test_all_natural_error_items_have_a_cut():
    for r in natural_error_items().itertuples():
        assert load_item(r.trace, r.ep_index).cut_idx is not None


def test_r1live_subset_seeded():
    s = r1live_subset()
    assert len(s) == 40 and s == r1live_subset() and set(s) <= set(main_items().item_id)
