"""R6 gate (plan 8.4; D11, D13), mock model only."""
import json

import litellm
import pytest

from src.replay.r6 import FIELD, PROMPT_SENTENCE, RETRY_MESSAGE, check, field_schema, run_r6, with_prompt_sentence
from src.replay.variants import build, load_item
from src.runner.item_lists import load_bait

ITEM_EX = "rep001_e03_alice"   # record extraction, validated bait
ITEM_DS = "rep004_e06_alice"   # data search, validated bait


def scripted(args_list):
    """Mock backend returning submit_verdict calls with the given argument dicts in order."""
    state = {"n": 0, "requests": []}

    def backend(**kw):
        state["requests"].append(kw)
        a = args_list[min(state["n"], len(args_list) - 1)]
        state["n"] += 1
        return litellm.ModelResponse(model="mock", choices=[{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": [{"id": f"call_{state['n']}", "type": "function",
                                                                  "function": {"name": "submit_verdict",
                                                                               "arguments": json.dumps(a)}}]}}],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    backend.state = state
    return backend


def _item(item_id):
    b = load_bait(item_id)
    ctx = load_item(b["trace"], b["ep_index"])
    return b, build(ctx, "CUT", bob_r1_content=b["bob_r1_content"])


def _good_ex(b):
    log = json.loads(b["bait_raw_log"])
    res = [e for e in log if e["tool"] == "resolve_records"][-1]
    sent = dict(zip([i["record_id"] for i in res["result"]["items"]], res["arguments"]["records"]))
    ans = json.loads([e for e in log if e["tool"] == "save_final_answer"][-1]["arguments"]["answer"])
    return {"records": [{"record_id": r, "quote": sent[r]} for r in ans]}


def test_schema_field_and_unchanged_messages():
    b, msgs = _item(ITEM_EX)
    msgs = with_prompt_sentence(msgs)
    be = scripted([{"reasoning": "r", "verdict": "reject"}])
    res = run_r6(msgs, "record_extraction", be, bob_r1_content=b["bob_r1_content"], raw_log=b["bait_raw_log"])
    req = be.state["requests"][0]
    props = req["tools"][0]["function"]["parameters"]["properties"]
    assert FIELD in props and set(req["tools"][0]["function"]["parameters"]["required"]) == {"reasoning", "verdict"}
    assert req["messages"] == msgs
    r6 = res.extra["r6"]
    assert r6["first_verdict"] == "reject" and not r6["gate_fired"] and r6["final_verdict"] == "reject"


def test_compliant_accept_passes():
    b, msgs = _item(ITEM_EX)
    be = scripted([{"reasoning": "r", "verdict": "accept", FIELD: _good_ex(b)}])
    r6 = run_r6(msgs, "record_extraction", be, bob_r1_content=b["bob_r1_content"],
                raw_log=b["bait_raw_log"]).extra["r6"]
    assert r6["first_check"]["compliant"] and not r6["gate_fired"] and r6["final_verdict"] == "accept"
    assert len(be.state["requests"]) == 1


@pytest.mark.parametrize("retry_ok,final", [(True, "accept"), (False, "reject")])
def test_gate_retry(retry_ok, final):
    b, msgs = _item(ITEM_EX)
    good = _good_ex(b)
    incomplete = {"records": good["records"][:-1]}
    be = scripted([{"reasoning": "r", "verdict": "accept", FIELD: incomplete},
                   {"reasoning": "r2", "verdict": "accept", FIELD: good if retry_ok else incomplete}])
    res = run_r6(msgs, "record_extraction", be, bob_r1_content=b["bob_r1_content"], raw_log=b["bait_raw_log"])
    r6 = res.extra["r6"]
    assert r6["first_verdict"] == "accept" and r6["gate_fired"] and r6["final_verdict"] == final
    assert res.verdict == final and len(be.state["requests"]) == 2
    retry_msgs = be.state["requests"][1]["messages"]
    tool = [m for m in retry_msgs if m.get("role") == "tool"][-1]
    assert json.loads(tool["content"]) == {"recorded": False, "error": RETRY_MESSAGE}
    assert retry_msgs[:len(msgs)] == msgs
    assert b["bait_id"] not in RETRY_MESSAGE


def test_quote_must_be_verbatim():
    b, _ = _item(ITEM_EX)
    good = _good_ex(b)
    bad = json.loads(json.dumps(good))
    bad["records"][0]["quote"] = bad["records"][0]["quote"] + " (paraphrased)"
    assert check(good, "record_extraction", b["bob_r1_content"], b["bait_raw_log"])["compliant"]
    c = check(bad, "record_extraction", b["bob_r1_content"], b["bait_raw_log"])
    assert not c["compliant"] and c["complete"] and not c["quotes_ok"]
    assert not check(None, "record_extraction", b["bob_r1_content"], b["bait_raw_log"])["compliant"]


def test_data_search_checker():
    b, _ = _item(ITEM_DS)
    log = json.loads(b["bait_raw_log"])
    ans = json.loads([e for e in log if e["tool"] == "save_final_answer"][-1]["arguments"]["answer"])
    keys = [str(list(r.values())[0]) for r in ans]
    good = {"keys": keys, "conditions": [b["relaxed_condition"]]}
    assert check(good, "data_search", b["bob_r1_content"], b["bait_raw_log"])["compliant"]
    assert not check({"keys": keys[:-1], "conditions": [b["relaxed_condition"]]}, "data_search",
                     b["bob_r1_content"], b["bait_raw_log"])["compliant"]
    assert not check({"keys": keys, "conditions": []}, "data_search", b["bob_r1_content"],
                     b["bait_raw_log"])["compliant"]
    assert not check({"keys": keys, "conditions": ["no_such_column = 'zzz'"]}, "data_search", b["bob_r1_content"],
                     b["bait_raw_log"])["compliant"]


def test_d13_prompt_sentence_only_change():
    """D13: R6 messages equal R1 (bait) / R0' (correct) except one sentence appended to the verdict prompt."""
    from src.runner.jobs import make_job
    from src.runner.item_lists import holdout_items
    for item in (ITEM_EX, ITEM_DS):
        b, cut = _item(item)
        r6 = with_prompt_sentence(cut)
        assert r6[:-1] == cut[:-1]
        assert r6[-1]["content"] == cut[-1]["content"].rstrip() + " " + PROMPT_SENTENCE
        assert cut[-1]["content"].count(PROMPT_SENTENCE) == 0
    for name in ("bob", "record", "key", "row"):   # the sentence names no record, key, or condition
        assert name not in PROMPT_SENTENCE.lower()
    row = holdout_items().iloc[0]
    for version in ("bait", "correct"):
        r6j, ref = make_job("T", row, "R6", version), make_job("T", row, "R1" if version == "bait" else "R0p", version)
        a, c = r6j.build_messages(), ref.build_messages()
        assert a[:-1] == c[:-1] and a[-1]["content"] == c[-1]["content"] + " " + PROMPT_SENTENCE


def test_d13_data_search_wording():
    d = field_schema("data_search")["description"]
    assert "the value of the answer key column for every row of Bob's final answer" in d
    assert "WHERE condition" in d
