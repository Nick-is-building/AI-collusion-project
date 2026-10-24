"""Replay-context unit tests (PROJECT_PLAN.md section 23.2; A01 task 4).

Run on all 168 candidates and the 63-case fidelity set. Requires data/raw/ (data/download.py).
"""
from pathlib import Path

import pandas as pd
import pytest

from src.replay.request import canonical_json, mock_backend, run_verdict
from src.replay.traces import ROUND_INSTRUCTION, load_trace, trace_files
from src.replay.variants import R4N_SYSTEM_PROMPT, build, load_item, no_round_instruction_after_cut

ITEMS = Path(__file__).resolve().parents[1] / "data" / "derived" / "items"
CAND = pd.read_csv(ITEMS / "candidates.csv")
FID = pd.read_csv(ITEMS / "fidelity_set.csv")


def signatures(messages):
    """Every thought-signature carrier in a message list, in order."""
    out = []
    for m in messages:
        for tc in m.get("tool_calls") or []:
            out.append(tc.get("id"))
            out.append(canonical_json(tc.get("provider_specific_fields")))
        if "provider_specific_fields" in m:
            out.append(canonical_json(m["provider_specific_fields"]))
    return out


def cand_items():
    return [load_item(r.trace, r.ep_index) for r in CAND.itertuples()]


@pytest.fixture(scope="module")
def candidates():
    return cand_items()


def test_stored_lists_are_cumulative():
    """results[e-1] messages are an exact prefix of results[e] (the slicing assumption)."""
    for f in trace_files():
        res = load_trace(f.name)["results"]
        for e in range(1, len(res)):
            for a in ("alice", "bob"):
                prev, cur = res[e - 1]["agents"][a]["messages"], res[e]["agents"][a]["messages"]
                assert cur[:len(prev)] == prev, (f.name, e, a)


def test_r0_byte_identical_with_signatures(candidates):
    fid = [load_item(r.trace, r.ep_index, r.judge) for r in FID.itertuples()]
    assert len(candidates) == 168 and len(fid) == 63
    n_sig = 0
    for c in candidates + fid:
        stored = c.messages[:c.verdict_prompt_idx + 1]
        built = build(c, "R0")
        assert canonical_json(built) == canonical_json(stored)
        assert signatures(built) == signatures(stored)
        n_sig += sum("__thought__" in str(s) for s in signatures(built))
    assert n_sig > 0


def test_cut_prefix_identical_and_no_round_instruction(candidates):
    for c in candidates:
        m = build(c, "CUT")
        assert len(m) == c.cut_idx + 2
        assert canonical_json(m[:c.cut_idx + 1]) == canonical_json(c.messages[:c.cut_idx + 1])
        assert signatures(m) == signatures(c.messages[:c.cut_idx + 1])
        assert m[-1] == c.messages[c.verdict_prompt_idx]
        bob = m[-2]
        assert bob["role"] == "user" and bob["content"].startswith("[round=1/5][from=bob]")
        assert not ROUND_INSTRUCTION.search(bob["content"])
        assert no_round_instruction_after_cut(m)
        # every kept assistant turn of the current episode precedes Bob's log
        assert all(i < c.cut_idx for i in range(c.ep_start, c.cut_idx) if m[i]["role"] == "assistant")


def test_bob_message_then_verdict_prompt_pattern(candidates):
    """Bob's (round-5) message directly before the true verdict prompt: 168 of 168 originals.

    The plan's "13 of 168" (sections 8.2, 23.2) comes from the pre-sprint substring rule, which in
    155 contexts takes a later channel message mentioning "verdict phase" for the verdict prompt.
    """
    orig = sum(c.messages[c.verdict_prompt_idx - 1]["role"] == "user"
               and "[from=bob]" in c.messages[c.verdict_prompt_idx - 1]["content"] for c in candidates)
    assert orig == 168
    sub = 0
    for c in candidates:
        first = next(i for i in range(c.ep_start, len(c.messages)) if c.messages[i]["role"] == "user"
                     and "verdict phase" in str(c.messages[i]["content"]))
        sub += c.messages[first - 1]["role"] == "user" and "[from=bob]" in c.messages[first - 1]["content"]
    assert sub == 13
    assert all(build(c, "CUT")[-2]["content"].startswith("[round=1/5][from=bob]") for c in candidates)


def test_verdict_prompt_is_exact_stored_prompt(candidates):
    for c in candidates:
        t = load_trace(c.trace)
        assert c.messages[c.verdict_prompt_idx]["content"] == t["results"][c.ep_index]["agents"]["bob"]["verdict_prompt"]


def test_r2_equals_current_episode_only(candidates):
    for c in candidates:
        m = build(c, "R2")
        manual = [c.messages[0]] + c.messages[c.ep_start:c.cut_idx + 1] + [c.messages[c.verdict_prompt_idx]]
        assert canonical_json(m) == canonical_json(manual)
        assert sum(x["content"].startswith("## Episode ") and "task phase" in x["content"][:40]
                   for x in m if x["role"] == "user") == 1


def test_r3_removes_only_earlier_communication(candidates):
    for c in candidates:
        m = build(c, "R3")
        cut = build(c, "CUT")
        heads = [x["content"].split("\n", 1)[0] for x in m if x["role"] == "user" and x["content"].startswith("## ")]
        n_ep = c.ep_index + 1
        assert sum("communication phase" in h for h in heads) == 1           # current episode only
        assert sum("verdict phase" in h for h in heads) == n_ep              # all verdict prompts kept
        assert sum("task phase" in h for h in heads) == n_ep
        # earlier episodes contain no channel messages and no send_message calls
        cur = next(i for i, x in enumerate(m) if x["role"] == "user" and "communication phase" in x["content"][:40])
        assert not any("[from=" in str(x.get("content")) for x in m[:cur] if x["role"] == "user")
        assert not any(tc["function"]["name"] == "send_message" for x in m[:cur] for tc in x.get("tool_calls") or [])
        # current episode identical to CUT
        assert canonical_json(m[cur:]) == canonical_json(cut[c.comm_opening_idx(c.ep_index):])


def test_r4_and_r4n_structure(candidates):
    for c in candidates:
        r4, r4n = build(c, "R4"), build(c, "R4n")
        assert [x["role"] for x in r4] == ["system", "user", "user", "user"]
        assert r4[0] == c.messages[0] and r4n[0] == {"role": "system", "content": R4N_SYSTEM_PROMPT}
        assert r4[1:] == r4n[1:]
        assert "communication phase" in r4[1]["content"][:40]
        assert r4[2] == c.messages[c.cut_idx] and r4[3] == c.messages[c.verdict_prompt_idx]


def test_bob_override_changes_only_bob_message(candidates):
    c = candidates[0]
    new = c.messages[c.cut_idx]["content"] + " X"
    for v in ("CUT", "R2", "R3", "R4", "R4n"):
        a, b = build(c, v), build(c, v, bob_r1_content=new)
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        assert len(a) == len(b) and len(diff) == 1 and b[diff[0]]["content"] == new
    with pytest.raises(ValueError):
        build(c, "R0", bob_r1_content=new)


def test_upstream_request_path_sends_built_messages(candidates):
    for c in candidates[:5]:
        for v in ("R0", "CUT", "R2", "R3", "R4", "R4n"):
            built = build(c, v)
            r = run_verdict(built, "data_search", mock_backend("accept"))
            assert r.verdict == "accept" and not r.forced and len(r.requests) == 1
            k = r.requests[0]
            assert canonical_json(k["messages"]) == canonical_json(built)
            assert k["model"] == "gemini/gemini-3.1-flash-lite" and k["temperature"] == 1.0
            assert k["max_tokens"] == 64000 and k["reasoning_effort"] == "high"
            assert k["tool_choice"] == {"type": "function", "function": {"name": "submit_verdict"}}
            assert [t["function"]["name"] for t in k["tools"]] == ["submit_verdict"]


def test_upstream_attempt_loop_and_forced_verdict(candidates):
    built = build(candidates[0], "CUT")
    r = run_verdict(built, "data_search", mock_backend("reject", fail_first=3))
    assert r.forced and r.verdict == "reject" and len(r.requests) == 3
    r = run_verdict(built, "data_search", mock_backend("reject", fail_first=1))
    assert not r.forced and r.verdict == "reject" and len(r.requests) == 2
