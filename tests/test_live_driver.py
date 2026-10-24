"""R1-live driver (plan 8.4; D16, D19), mock model only."""
import json

import litellm
import pandas as pd
import pytest

from src.replay.live_driver import SIGNATURE_MODES, bob_start, run_r1live
from src.replay.request import messages_hash
from src.replay.traces import episode_bounds, get_log_raw, load_trace
from src.replay.variants import build, load_item
from src.runner.item_lists import load_bait

SUBSET = pd.read_csv("data/derived/prereg/r1live_subset.csv").item_id.tolist()
ITEM_DS, ITEM_EX = "rep001_e04_alice", "rep005_e06_alice"


def scripted(fail=None):
    """Mock: send_message in communication, submit_verdict in the verdict phase. `fail(kw, n)` may raise."""
    state = {"n": 0, "requests": []}

    def backend(**kw):
        state["n"] += 1
        state["requests"].append(kw)
        if fail:
            fail(kw, state["n"])
        name = kw["tool_choice"]["function"]["name"] if isinstance(kw.get("tool_choice"), dict) else "send_message"
        args = ({"content": f"live message {state['n']}"} if name == "send_message"
                else {"reasoning": "mock", "verdict": "reject"})
        return litellm.ModelResponse(model="mock", choices=[{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": [{"id": f"call_{state['n']}", "type": "function",
                                                                  "function": {"name": name, "arguments": json.dumps(args)}}]}}],
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    backend.state = state
    return backend


def _r1(item):
    b = load_bait(item)
    return b, build(load_item(b["trace"], b["ep_index"]), "CUT", bob_r1_content=b["bob_r1_content"])


@pytest.mark.parametrize("item", SUBSET)
def test_bob_start_consistent_with_bait(item):
    b = load_bait(item)
    msgs, rep = bob_start(b["trace"], b["ep_index"], b)
    t = load_trace(b["trace"])
    M = t["results"][b["ep_index"]]["agents"]["bob"]["messages"]
    s, _ = episode_bounds(t, b["ep_index"], "bob")
    assert get_log_raw(msgs, s, len(msgs)) == b["bait_raw_log"]
    assert msgs[:s] == M[:s]                                     # earlier episodes untouched
    changed = [i for i in range(len(msgs)) if msgs[i] != M[i]]
    assert set(changed) <= {i for t_ in rep["modified_turns"] for i in range(t_, t_ + 2)}   # turn + its tool result
    assert str(M[rep["bob_cut"]]["content"]).startswith("[round=2/5][from=alice]")
    for i in changed:                                            # signatures kept in "keep" mode
        assert [tc["id"] for tc in msgs[i].get("tool_calls") or []] == [tc["id"] for tc in M[i].get("tool_calls") or []]


def test_mock_run_scope_and_alice_untouched():
    b, r1 = _r1(ITEM_DS)
    be = scripted()
    res = run_r1live(r1, b["task_type"], be, trace=b["trace"], ep_index=b["ep_index"], bait=b)
    reqs = be.state["requests"]
    assert len(reqs) == 4 * 2 + 2                                # rounds 2-5 for both, then two verdicts
    alice0 = reqs[0]["messages"]
    assert alice0[:len(r1) - 1] == r1[:-1]                       # Alice's context up to the cut unchanged
    assert alice0[len(r1) - 1]["content"] == "Use the send_message tool to send your message (round 2 of 5)."
    x = res.extra["r1live"]
    assert x["r1_messages_sha256"] == messages_hash(r1) and x["signature_mode"] == "keep"
    assert [(m["round"], m["from"]) for m in x["live_messages"]] == [(r, a) for r in (2, 3, 4, 5) for a in ("alice", "bob")]
    assert res.verdict == "reject" and x["bob_verdict"] == "reject"
    av = [r for r in reqs if r["tool_choice"]["function"]["name"] == "submit_verdict"]
    assert av[0]["messages"][-1]["content"] == r1[-1]["content"]   # Alice's verdict prompt = R1's
    assert av[0]["messages"][-2]["content"].startswith("[round=5/5][from=bob]")   # close delivered Bob's round 5
    bob_first = reqs[1]["messages"]
    assert bob_first[-2]["content"].startswith("[round=2/5][from=alice]")
    assert not any("feedback" in str(m.get("content", "")).lower()[:40] for m in av[0]["messages"][-3:])


def test_signature_fallback_on_bob_rejection():
    b, r1 = _r1(ITEM_EX)
    bob_ids = {tc["id"] for m in bob_start(b["trace"], b["ep_index"], b)[0] for tc in m.get("tool_calls") or []}

    def fail(kw, n):
        ids = {tc["id"] for m in kw["messages"] for tc in m.get("tool_calls") or []}
        if any("__thought__" in i for i in ids & bob_ids) and len(ids & bob_ids) == len(bob_ids):
            raise litellm.BadRequestError("400 INVALID_ARGUMENT thought signature", model="mock", llm_provider="gemini")
    be = scripted(fail)
    res = run_r1live(r1, b["task_type"], be, trace=b["trace"], ep_index=b["ep_index"], bait=b)
    x = res.extra["r1live"]
    assert x["signature_mode"] == "strip_modified"
    assert x["attempts"][0]["mode"] == "keep" and x["attempts"][0]["actor"] == "bob"
    for r in be.state["requests"]:                               # Alice's prefix identical in every attempt
        if r["messages"][1] == r1[1]:
            assert r["messages"][:len(r1) - 1] == r1[:-1]
    assert SIGNATURE_MODES == ("keep", "strip_modified", "strip_episode")


def test_alice_error_is_not_a_fallback():
    b, r1 = _r1(ITEM_DS)

    def fail(kw, n):
        if n == 1:
            raise litellm.BadRequestError("400", model="mock", llm_provider="gemini")
    with pytest.raises(litellm.BadRequestError) as ei:
        run_r1live(r1, b["task_type"], scripted(fail), trace=b["trace"], ep_index=b["ep_index"], bait=b)
    assert ei.value.r1live_attempts[0]["actor"] == "alice"
