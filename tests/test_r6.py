"""R6 gate (plan 8.4; D11, D12), mock model only."""
import json

import litellm
import pytest

from src.replay.r6 import FIELD, RETRY_MESSAGE, check, run_r6
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
    be = scripted([{"reasoning": "r", "verdict": "reject"}])
    res = run_r6(msgs, "record_extraction", be, bob_r1_content=b["bob_r1_content"], raw_log=b["bait_raw_log"])
    req = be.state["requests"][0]
    props = req["tools"][0]["function"]["parameters"]["properties"]
    assert FIELD in props and set(req["tools"][0]["function"]["parameters"]["required"]) == {"reasoning", "verdict"}
    assert req["messages"] == msgs          # D12: context and verdict prompt identical to R1
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
