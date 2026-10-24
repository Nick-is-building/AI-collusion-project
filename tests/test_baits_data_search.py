"""Data-search baits (deviation D2; plan section 8.3, 23.2). Requires data/raw/ and the upstream
database. Saved baits must rebuild byte-identically, pass rules 1-3, and change only Bob's round-1
message in every replay variant."""
import hashlib
import json
from pathlib import Path

import pytest

from src.replay import baits_data_search as ds
from src.replay.bait_common import Ambiguous
from src.replay.variants import build, load_item

B = Path(__file__).resolve().parents[1] / "data" / "derived" / "baits"
SAVED = sorted(p for p in B.glob("*.json") if json.loads(p.read_text())["task_type"] == "data_search")


def test_some_data_search_baits_exist():
    assert len(SAVED) >= 1


@pytest.mark.parametrize("path", SAVED, ids=[p.stem for p in SAVED])
def test_saved_bait_reproducible_and_valid(path):
    rec = json.loads(path.read_text())
    b = ds.build_bait(rec["trace"], rec["ep_index"], rec["count_mode"])
    assert b["bob_r1_content"] == rec["bob_r1_content"] and b["new_raw_log"] == rec["bait_raw_log"]
    assert hashlib.sha256(b["bob_r1_content"].encode()).hexdigest() == rec["bob_r1_content_sha256"]
    assert all(ds.validate(b, rec["trace"], rec["ep_index"]).values())
    task = ds.manifest()[rec["task_id"]]
    # rule 1 with Shi et al.'s evaluator; the original answer passes
    assert b["evaluator"]["extra_rows"] == [(rec["bait_id"],)] and b["evaluator"]["missing_row_count"] == 0
    orig_save = [e for e in json.loads(b["original_raw_log"]) if e["tool"] == "save_final_answer"][-1]
    from experiments.evaluation import evaluate_data_search_artifact
    assert evaluate_data_search_artifact(task, {"data_search_artifact": {"answer": orig_save["arguments"]["answer"]}},
                                         ds.UP)["quality_verdict"] == "pass"
    # the relaxed query really returns the bait result on the database; the relaxed row violates the
    # original condition (the original query does not return it)
    log = json.loads(b["new_raw_log"])
    q = [e for e in log if e["tool"] == "query_database" and e.get("seq") == rec["answer_query_seq"]][0]
    assert ds.run_query(task, q["arguments"]["sql"]) == q["result"]
    assert rec["relaxed_condition"] in q["arguments"]["sql"] and rec["original_condition"] not in q["arguments"]["sql"]
    orig_sql = q["arguments"]["sql"].replace(rec["relaxed_condition"], rec["original_condition"])
    assert rec["added_row"] not in ds.run_query(task, orig_sql)["rows"]
    # the original condition's literal is stated in the search prompt; the relaxed one is not
    assert ds.literal_in_prompt(rec["violated_literal"], task["search_prompt"])
    # only Bob's round-1 message differs in Alice's replay contexts
    ctx = load_item(rec["trace"], rec["ep_index"])
    for variant in ("CUT", "R2", "R3", "R4", "R4n"):
        a, c = build(ctx, variant), build(ctx, variant, bob_r1_content=rec["bob_r1_content"])
        assert sum(x != y for x, y in zip(a, c)) == 1 and len(a) == len(c)


def test_conjunct_parsing():
    w = "a.d BETWEEN '2025-01-01' AND '2025-06-30' AND a.s IN ('x', 'y_z') AND (a.h IS NULL OR a.h > 7) AND a.n >= 2"
    cs = ds.conjuncts(w)
    assert cs == ["a.d BETWEEN '2025-01-01' AND '2025-06-30'", "a.s IN ('x', 'y_z')", "(a.h IS NULL OR a.h > 7)", "a.n >= 2"]
    assert ds.parse(cs[0])["kind"] == "between" and ds.parse(cs[1])["lits"] == ["'x'", "'y_z'"]
    assert ds.parse(cs[2]) is None and ds.parse(cs[3])["op"] == ">="
    assert ds.parse("a.amount > d.budget") is None
    sql = "SELECT DISTINCT t.id FROM t JOIN u ON t.k = u.k WHERE t.a = 'it''s' AND t.b < 3 ORDER BY t.id;"
    s0, s1 = ds.select_span(sql)
    assert sql[s0:s1].strip() == "t.id"
    w0, w1 = ds.where_span(sql)
    assert ds.conjuncts(sql[w0:w1]) == ["t.a = 'it''s'", "t.b < 3"]


def test_literal_in_prompt():
    p = "cases from 2025-01-01 through 2025-06-30 that are open or pending review, severity at least 2, $20,000+"
    assert ds.literal_in_prompt("'pending_review'", p) and ds.literal_in_prompt("'open'", p)
    assert ds.literal_in_prompt("2", p) and ds.literal_in_prompt("20000", p)
    assert ds.literal_in_prompt("'2025-06-30'", p)
    assert not ds.literal_in_prompt("'closed'", p) and not ds.literal_in_prompt("3", p)
    assert not ds.literal_in_prompt("'pen'", p)


def test_states_condition():
    f = {"conj": "T.d BETWEEN '2025-01-01' AND '2025-06-30'", "violated_literal": "'2025-06-30'"}
    assert ds.states_condition("filtered 2025-01-01 to 2025-06-30", f)
    assert ds.states_condition("used t.d between '2025-01-01'  and '2025-06-30'", f)
    assert not ds.states_condition("filtered by date", f)
    g = {"conj": "s IN ('open', 'pending_review')", "violated_literal": "'open', 'pending_review'"}
    assert ds.states_condition("status open or pending review", g) and not ds.states_condition("status open", g)
