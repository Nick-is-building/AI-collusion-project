"""R6x exhaustive source classification gate (D30) and the A08 job list (D30, D31); mock model only."""
import collections
import json

import pytest

from scripts.a06.launch_addendum import omission_items
from scripts.a08.launch_r6x import first_jobs, jobs
from src.replay import r6x
from src.replay.r6x import FIELD, PROMPT_SENTENCE, RETRY_MESSAGE, check, label_of, run_r6x, source_sentences, \
    with_prompt_sentence
from src.replay.variants import build, load_item
from src.runner.jobs import original_bob_message
from tests.test_r6 import scripted

ITEM = "rep001_e03_alice"


def _om():
    return {o["item_id"]: o for o in omission_items()}[ITEM]


def _ctx(o):
    return with_prompt_sentence(build(load_item(o["trace"], o["ep_index"]), "CUT", bob_r1_content=o["bob_r1_content"]))


def _full(o, removed_label="include"):
    return [{"sentence": s, "label": removed_label if s == o["removed_sentence"] else "exclude"}
            for s in source_sentences(o["omission_raw_log"])]


def _run(args_list):
    o = _om()
    be = scripted(args_list)
    res = run_r6x(_ctx(o), "record_extraction", be, bob_r1_content=o["bob_r1_content"], raw_log=o["omission_raw_log"])
    return res, be


def test_source_sentences_all_items():
    for o in omission_items():
        s = source_sentences(o["omission_raw_log"])
        assert 16 <= len(s) <= 24 and len(set(s)) == len(s) and o["removed_sentence"] in s
        _, raw = original_bob_message(o["trace"], int(o["ep_index"]))
        assert source_sentences(raw) == s   # read_source is identical in the correct version


def test_schema_and_prompt_sentence_only_change():
    o = _om()
    res, be = _run([{"reasoning": "r", "verdict": "reject", FIELD: _full(o)}])
    req = be.state["requests"][0]
    fn = [t for t in req["tools"] if t["function"]["name"] == "submit_verdict"][0]["function"]
    f = fn["parameters"]["properties"][FIELD]
    assert f["type"] == "array" and f["items"]["properties"]["label"]["enum"] == ["include", "exclude"]
    assert FIELD in fn["parameters"]["required"]
    r1 = build(load_item(o["trace"], o["ep_index"]), "CUT", bob_r1_content=o["bob_r1_content"])
    assert req["messages"][:-1] == r1[:-1]
    assert req["messages"][-1]["content"] == r1[-1]["content"].rstrip() + " " + PROMPT_SENTENCE
    out = res.extra["r6x"]
    assert out["first_verdict"] == "reject" and out["first_check"]["compliant"] and not out["gate_fired"]
    assert len(be.state["requests"]) == 1


def test_check_rules():
    o = _om()
    raw = o["omission_raw_log"]
    full = _full(o)
    assert check(full, raw)["compliant"]
    assert check(list(reversed(full)), raw)["compliant"]                      # order not checked
    assert check([dict(e, sentence="  " + e["sentence"] + " ") for e in full], raw)["compliant"]  # outer whitespace
    assert check([dict(e, label="Include") for e in full], raw)["compliant"]  # case-insensitive label
    c = check(full[1:], raw)
    assert not c["compliant"] and c["missing"] == [full[0]["sentence"]]
    c = check(full + [full[0]], raw)
    assert not c["compliant"] and c["duplicated"] == [full[0]["sentence"]]
    c = check(full + [{"sentence": "Made-up sentence.", "label": "exclude"}], raw)
    assert not c["compliant"] and c["n_extra"] == 1 and c["compliant_ignoring_extra"]
    c = check([dict(full[0], sentence=full[0]["sentence"][:-1])] + full[1:], raw)   # not verbatim
    assert not c["compliant"] and c["missing"] and c["n_extra"] == 1
    c = check([dict(full[0], label="maybe")] + full[1:], raw)
    assert not c["compliant"] and c["bad_labels"]
    assert not check(None, raw)["present"] and not check([], raw)["compliant"]
    assert not check(["a bare string"] * 3, raw)["compliant"]


def test_label_of():
    o = _om()
    s = o["removed_sentence"]
    assert label_of(_full(o, "include"), s) == "include"
    assert label_of(_full(o, "exclude"), s) == "exclude"
    assert label_of([e for e in _full(o) if e["sentence"] != s], s) == "not listed"
    assert label_of(_full(o) + [{"sentence": s, "label": "exclude"}], s) == "conflicting"
    assert label_of(None, s) == "not listed"


def test_compliant_accept_passes():
    o = _om()
    res, be = _run([{"reasoning": "r", "verdict": "accept", FIELD: _full(o, "exclude")}])
    assert res.extra["r6x"]["final_verdict"] == "accept" and len(be.state["requests"]) == 1


@pytest.mark.parametrize("retry_ok,retry_verdict,final", [(True, "accept", "accept"), (False, "accept", "reject"),
                                                          (False, "reject", "reject")])
def test_gate_retry_on_noncompliant_accept(retry_ok, retry_verdict, final):
    o = _om()
    res, be = _run([{"reasoning": "r", "verdict": "accept", FIELD: _full(o)[2:]},
                    {"reasoning": "r2", "verdict": retry_verdict, FIELD: _full(o) if retry_ok else []}])
    out = res.extra["r6x"]
    assert out["first_verdict"] == "accept" and out["gate_fired"] and out["final_verdict"] == final
    assert res.verdict == final and len(be.state["requests"]) == 2
    tool = [m for m in be.state["requests"][1]["messages"] if m.get("role") == "tool"][-1]
    assert json.loads(tool["content"]) == {"recorded": False, "error": RETRY_MESSAGE}


def test_noncompliant_reject_not_retried():
    res, be = _run([{"reasoning": "r", "verdict": "reject", FIELD: []}])
    out = res.extra["r6x"]
    assert out["final_verdict"] == "reject" and not out["gate_fired"] and not out["first_check"]["compliant"]
    assert len(be.state["requests"]) == 1


def test_retry_message_sentence_and_schema_name_no_sentence():
    for o in omission_items():
        srcs = source_sentences(o["omission_raw_log"])
        for text in (RETRY_MESSAGE, PROMPT_SENTENCE, json.dumps(r6x.field_schema())):
            assert o["removed_id"] not in text and not any(s in text for s in srcs)


def test_job_list():
    js = jobs()
    n = len(omission_items())
    c = collections.Counter((j.check, j.variant, j.version) for j in js)
    assert c == {("R6X", "R6x", "omission"): 2 * n, ("R6X", "R6x", "correct"): 2 * n, ("R6COR", "R6", "correct"): 2 * n}
    assert len({j.call_id("a08") for j in js}) == len(js) == 6 * n
    fc = collections.Counter((j.variant, j.version) for j in first_jobs())
    assert len(fc) == 3 and min(fc.values()) >= 5


def test_job_contexts():
    om = _om()
    by = {(j.variant, j.version): j for j in jobs() if j.item_id == ITEM}
    r1 = build(load_item(om["trace"], om["ep_index"]), "CUT", bob_r1_content=om["bob_r1_content"])
    r0p = build(load_item(om["trace"], om["ep_index"]), "CUT")
    m = by[("R6x", "omission")].build_messages()
    assert m[:-1] == r1[:-1] and m[-1]["content"].endswith(PROMPT_SENTENCE)
    m = by[("R6x", "correct")].build_messages()
    assert m[:-1] == r0p[:-1] and m[-1]["content"].endswith(PROMPT_SENTENCE)
    content, raw = original_bob_message(om["trace"], om["ep_index"])
    assert by[("R6x", "correct")].verdict_fn.keywords == {"bob_r1_content": content, "raw_log": raw}
    assert by[("R6x", "omission")].verdict_fn.keywords["raw_log"] == om["omission_raw_log"]
    from src.replay.r6 import PROMPT_SENTENCE as R6_SENTENCE, run_r6
    j = by[("R6", "correct")]
    m = j.build_messages()
    assert m[:-1] == r0p[:-1] and m[-1]["content"].endswith(R6_SENTENCE)
    assert j.verdict_fn.func is run_r6 and j.verdict_fn.keywords == {"bob_r1_content": content, "raw_log": raw}
