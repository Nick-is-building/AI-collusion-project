"""R6s source-enumeration gate (D28 = A07 "D27", sentence-only amendment) and the A07 job list; mock model only."""
import collections
import json

import pytest

from scripts.a06.launch_addendum import omission_items
from scripts.a07.launch_r6s import first_jobs, jobs
from src.replay import r6s
from src.replay.r6s import FIELD, PROMPT_SENTENCE, RETRY_MESSAGE, check, run_r6s, with_prompt_sentence
from src.replay.variants import build, load_item
from src.runner.jobs import original_bob_message
from tests.test_r6 import scripted

ITEM = "rep001_e03_alice"


def _om():
    return {o["item_id"]: o for o in omission_items()}[ITEM]


def _ctx(o):
    return with_prompt_sentence(build(load_item(o["trace"], o["ep_index"]), "CUT", bob_r1_content=o["bob_r1_content"]))


def _source_lines(o):
    log = json.loads(o["omission_raw_log"])
    return [l for l in log[0]["result"]["content"].split("\n") if l.strip()]


def _run(args_list):
    o = _om()
    be = scripted(args_list)
    res = run_r6s(_ctx(o), "record_extraction", be, bob_r1_content=o["bob_r1_content"], raw_log=o["omission_raw_log"])
    return res, be


def test_schema_and_prompt_sentence_only_change():
    o = _om()
    res, be = _run([{"reasoning": "r", "verdict": "reject", FIELD: [o["removed_sentence"]]}])
    req = be.state["requests"][0]
    fn = [t for t in req["tools"] if t["function"]["name"] == "submit_verdict"][0]["function"]
    assert fn["parameters"]["properties"][FIELD]["items"] == {"type": "string"}
    assert FIELD in fn["parameters"]["required"]
    r1 = build(load_item(o["trace"], o["ep_index"]), "CUT", bob_r1_content=o["bob_r1_content"])
    assert req["messages"][:-1] == r1[:-1]
    assert req["messages"][-1]["content"] == r1[-1]["content"].rstrip() + " " + PROMPT_SENTENCE
    out = res.extra["r6s"]
    assert out["first_verdict"] == "reject" and out["first_check"]["compliant"] and not out["gate_fired"]
    assert len(be.state["requests"]) == 1


def test_omitted_sentence_passes_gate_and_is_visible():
    o = _om()
    assert o["removed_id"] not in json.loads(o["omission_raw_log"])[0]["result"]["content"]
    c = check(_source_lines(o), o["bob_r1_content"], o["omission_raw_log"])
    assert c["compliant"] and o["removed_sentence"] in _source_lines(o)


def test_check_rules():
    o = _om()
    args = (o["bob_r1_content"], o["omission_raw_log"])
    assert not check([], *args)["compliant"]
    assert not check(None, *args)["present"]
    assert check(["Made-up sentence not in the log."], *args)["bad_sentences"]
    assert not check([""], *args)["compliant"]


def test_compliant_accept_passes():
    o = _om()
    res, be = _run([{"reasoning": "r", "verdict": "accept", FIELD: _source_lines(o)[:3]}])
    assert res.extra["r6s"]["final_verdict"] == "accept" and len(be.state["requests"]) == 1


@pytest.mark.parametrize("retry_ok,final", [(True, "accept"), (False, "reject")])
def test_gate_retry_on_noncompliant_accept(retry_ok, final):
    o = _om()
    bad = ["Not a sentence from the source."]
    res, be = _run([{"reasoning": "r", "verdict": "accept", FIELD: bad},
                    {"reasoning": "r2", "verdict": "accept", FIELD: _source_lines(o)[:2] if retry_ok else []}])
    out = res.extra["r6s"]
    assert out["first_verdict"] == "accept" and out["gate_fired"] and out["final_verdict"] == final
    assert res.verdict == final and len(be.state["requests"]) == 2
    tool = [m for m in be.state["requests"][1]["messages"] if m.get("role") == "tool"][-1]
    assert json.loads(tool["content"]) == {"recorded": False, "error": RETRY_MESSAGE}


def test_noncompliant_reject_not_retried():
    res, be = _run([{"reasoning": "r", "verdict": "reject", FIELD: []}])
    out = res.extra["r6s"]
    assert out["final_verdict"] == "reject" and not out["gate_fired"] and not out["first_check"]["compliant"]
    assert len(be.state["requests"]) == 1


def test_retry_message_and_sentence_name_no_record():
    for o in omission_items():
        for text in (RETRY_MESSAGE, PROMPT_SENTENCE, json.dumps(r6s.field_schema())):
            assert o["removed_id"] not in text and o["removed_sentence"] not in text


def test_job_list():
    js = jobs()
    n = len(omission_items())
    c = collections.Counter((j.check, j.variant, j.version) for j in js)
    assert c == {("R6S", "R6s", "omission"): 2 * n, ("R6S", "R6s", "correct"): 2 * n, ("R6OM", "R6", "omission"): 2 * n}
    assert len({j.call_id("a07") for j in js}) == len(js) == 6 * n
    fc = collections.Counter((j.variant, j.version) for j in first_jobs())
    assert len(fc) == 3 and min(fc.values()) >= 5


def test_job_contexts():
    om = _om()
    by = {(j.variant, j.version): j for j in jobs() if j.item_id == ITEM}
    r1 = build(load_item(om["trace"], om["ep_index"]), "CUT", bob_r1_content=om["bob_r1_content"])
    r0p = build(load_item(om["trace"], om["ep_index"]), "CUT")
    m = by[("R6s", "omission")].build_messages()
    assert m[:-1] == r1[:-1] and m[-1]["content"].endswith(PROMPT_SENTENCE)
    m = by[("R6s", "correct")].build_messages()
    assert m[:-1] == r0p[:-1] and m[-1]["content"].endswith(PROMPT_SENTENCE)
    content, raw = original_bob_message(om["trace"], om["ep_index"])
    assert by[("R6s", "correct")].verdict_fn.keywords == {"bob_r1_content": content, "raw_log": raw}
    assert by[("R6s", "omission")].verdict_fn.keywords["raw_log"] == om["omission_raw_log"]
    from src.replay.r6 import PROMPT_SENTENCE as R6_SENTENCE
    m = by[("R6", "omission")].build_messages()
    assert m[:-1] == r1[:-1] and m[-1]["content"].endswith(R6_SENTENCE)
