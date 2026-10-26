"""A17 (D41): Claude Haiku 5.5 route on the D25 contexts. No network: mock backends and LiteLLM's offline
raw-request builder only (a dummy API key is set in the test environment; the real key is never read)."""
from __future__ import annotations

import collections
import json
import re

import numpy as np
import pytest

from scripts.a06.launch_addendum import omission_items
from scripts.a17 import launch_a17 as L
from src.replay import a10, a17
from src.replay.a17_cells import COR_VARIANTS, FLASH_LITE_SOURCE, OM_VARIANTS, build_messages
from src.replay.request import canonical_json, messages_hash, mock_backend, run_verdict
from src.runner.costs import iter_call_lines
from src.runner.estimates import input_tokens

OM = omission_items()
CELLS = [(v, "omission") for v in OM_VARIANTS] + [(v, "correct") for v in COR_VARIANTS]


@pytest.fixture(scope="module")
def logged():
    out = collections.defaultdict(set)
    for r in iter_call_lines("results/raw"):
        if r.get("mode") == "live" and r.get("stage") in ("a06", "a13", "a14", "main"):
            out[(r["stage"], r.get("check"), r["item_id"], r["variant"], r["version"])].add(r["messages_sha256"])
    return out


def test_contexts_equal_the_flash_lite_contexts(logged):
    for o in OM:
        for v, ver in CELLS:
            h = messages_hash(build_messages(o, v, ver))
            src = [logged[(st, ck, o["item_id"], fv, ver)] for st, ck, fv in FLASH_LITE_SOURCE[(v, ver)]]
            assert any(h in s for s in src), (o["item_id"], v, ver)


def _upstream_request(msgs):
    return run_verdict(msgs, "record_extraction", mock_backend("accept"), judge="alice", episode_id="t").requests[0]


def test_a17_request_is_the_flash_lite_request_and_the_conversion_keeps_every_text(tmp_path, monkeypatch):
    """All 50 items x 8 cells: the upstream request built in the A17 path equals the Flash-Lite request; after removing
    signatures and renaming IDs, every message text is identical."""
    monkeypatch.setenv("A10_GUARD_DIR", str(tmp_path))
    seen = []

    def capture(**kw):
        seen.append(kw)
        return mock_backend("accept")(**kw)
    for o in OM:
        for v, ver in CELLS:
            msgs = build_messages(o, v, ver)
            seen.clear()
            res = a17.run(msgs, "record_extraction", capture, judge="alice", model=a17.MODEL_HAIKU, episode_id="t")
            fl = _upstream_request(msgs)
            assert canonical_json(res.requests[0]) == canonical_json(fl), (o["item_id"], v, ver)
            conv = seen[0]["messages"]
            assert a17.text_view(conv) == a17.text_view(fl["messages"])
            s = json.dumps(conv)
            assert a17.SIG_MARK not in s and "provider_specific_fields" not in s and "thought_signatures" not in s
            ids = [tc["id"] for m in conv for tc in m.get("tool_calls") or []]
            assert all(re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids) and len(set(ids)) == len(ids)
            assert {m["tool_call_id"] for m in conv if m["role"] == "tool"} <= set(ids)
            assert seen[0]["model"] == a17.MODEL_HAIKU and seen[0]["tool_choice"] == "auto"
            assert "temperature" not in seen[0] and seen[0]["thinking"] == {"type": "adaptive"}
            assert res.extra["a17"]["label"] == a17.LABEL


def _texts_openai(messages):
    out = []
    for m in messages:
        if m["role"] == "system":
            continue
        if m["role"] == "tool":
            out.append(("tool_result", m["content"]))
            continue
        if m.get("content"):
            out.append(("text", m["content"]))
        for tc in m.get("tool_calls") or []:
            out.append(("tool_use", tc["function"]["name"], json.loads(tc["function"]["arguments"])))
    return out


def _texts_anthropic(body):
    out = []
    for m in body["messages"]:
        blocks = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        for b in blocks:
            if b["type"] == "text":
                out.append(("text", b["text"]))
            elif b["type"] == "tool_use":
                out.append(("tool_use", b["name"], b["input"]))
            elif b["type"] == "tool_result":
                c = b["content"]
                out.append(("tool_result", c if isinstance(c, str) else "".join(x.get("text", "") for x in c)))
            else:
                raise AssertionError(b["type"])
    return out


def test_raw_anthropic_body_on_all_contexts(monkeypatch):
    """LiteLLM's Anthropic transformation (offline): system field, every text unchanged and in order, parameters."""
    from litellm.types.utils import CallTypes
    from litellm.utils import return_raw_request
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-offline-test-key")
    for o in OM:
        for v, ver in CELLS:
            fl = _upstream_request(build_messages(o, v, ver))
            ak = a17.anthropic_kwargs(fl)
            raw = return_raw_request(CallTypes.completion, dict(ak))
            assert "raw_request_body" in raw, raw.get("error")
            body = raw["raw_request_body"]
            assert raw["raw_request_api_base"] == "https://api.anthropic.com/v1/messages"
            assert body["model"] == "claude-haiku-5-5" and body["max_tokens"] == 64000
            assert body["tool_choice"] == {"type": "auto"} and body["thinking"] == {"type": "adaptive"}
            assert body["output_config"] == {"effort": "high"}
            assert not {"temperature", "top_p", "top_k"} & set(body)
            sysmsg = [m["content"] for m in fl["messages"] if m["role"] == "system"]
            assert [b["text"] for b in body["system"]] == sysmsg
            assert _texts_anthropic(body) == _texts_openai(fl["messages"]), (o["item_id"], v, ver)
            assert [t["name"] for t in body["tools"]] == ["submit_verdict"]
            roles = [m["role"] for m in body["messages"]]
            assert all(a != b for a, b in zip(roles, roles[1:])) and roles[0] == "user"


def test_no_context_above_the_haiku_window():
    # Flash-Lite input tokens per context (estimates table) x 2 (generous tokenizer margin) < 1,000,000
    worst = max(input_tokens(o["item_id"], b) for o in OM for b in ("CUT", "R4", "R2"))
    assert 2 * worst < 1_000_000


def test_jobs_order_ids_p6():
    js = L.jobs(drop_draw2=False)
    assert len(js) == 800 and len({j.item_id for j in js}) == 50
    ids = [j.call_id("a17") for j in js]
    assert len(set(ids)) == 800
    assert all(re.fullmatch(r"a17:HAIKU:rep\d{3}_e\d{2}_alice:(R1|R4|R2|R1\+CHK|R0p):(omission|correct):[12]", c)
               for c in ids)
    assert collections.Counter((j.variant, j.version) for j in js) == {c: 100 for c in CELLS}
    seen, prev = set(), None
    for j in js:
        if j.item_id != prev:
            assert j.item_id not in seen
            seen.add(j.item_id)
            prev = j.item_id
    rng = np.random.default_rng(2026)
    perm = rng.permutation(50)
    assert list(dict.fromkeys(j.item_id for j in js)) == [OM[i]["item_id"] for i in perm]
    cells = L.item_cells()
    k = rng.permutation(16)
    assert [(j.variant, j.version, j.draw) for j in js[:16]] == [cells[i] for i in k]
    assert all(j.model == a17.MODEL_HAIKU for j in js)
    first = L.first_jobs()
    assert len(first) == 48 and {j.item_id for j in first} == {OM[i]["item_id"] for i in perm[:3]}
    p6 = L.p6_jobs()
    assert len(p6) == 10 and not {j.item_id for j in p6} & {j.item_id for j in first}
    assert all(j.call_id("a17").startswith("a17:P6:") and j.variant == "R1" and j.version == "omission" for j in p6)
    assert len(L.jobs(drop_draw2=True)) == 400


class _Err(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status_code = status


def test_guard_billing_rate_limit_and_model(tmp_path):
    def billing(**kw):
        raise _Err("Your credit balance is too low to access the Anthropic API.")
    with pytest.raises(a17.StopA17):
        a17.guard_backend(billing, d=tmp_path)(model="m")
    assert a10.stop_file(tmp_path).exists()
    a10.stop_file(tmp_path).unlink()

    def rl(**kw):
        raise _Err("429 rate_limit_error", status=429)
    g = a17.guard_backend(rl, d=tmp_path)
    for _ in range(10):
        with pytest.raises(_Err):
            g(model="m")
    with pytest.raises(a10.StopA10):
        g(model="m")
    a10.stop_file(tmp_path).unlink()
    (tmp_path / "quota_429.jsonl").unlink()

    class R:
        model = "claude-sonnet-5-5"
    a17.guard_backend(lambda **kw: R(), d=tmp_path)(model="m")
    assert "response model" in a10.stop_file(tmp_path).read_text()


def test_no_tool_call_retry_uses_upstream_attempts(tmp_path, monkeypatch):
    """tool_choice auto: a text-only answer is followed by upstream's next verdict attempt."""
    import litellm
    monkeypatch.setenv("A10_GUARD_DIR", str(tmp_path))
    n = {"k": 0}
    seen = []

    def be(**kw):
        seen.append(kw)
        n["k"] += 1
        if n["k"] == 1:
            return litellm.ModelResponse(model="claude-haiku-5-5", choices=[{"message": {"role": "assistant",
                                         "content": "I think Bob is fine."}, "finish_reason": "stop"}],
                                         usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        return mock_backend("reject")(**kw)
    res = a17.run(build_messages(OM[0], "R1", "omission"), "record_extraction", be, episode_id="t")
    assert res.verdict == "reject" and not res.forced and len(seen) == 2
    assert len(seen[1]["messages"]) > len(seen[0]["messages"])


def test_mock_runner_stage1_slice(tmp_path, monkeypatch):
    from src.runner.runner import Runner
    monkeypatch.setenv("A10_GUARD_DIR", str(tmp_path / "guard"))
    js = L.first_jobs()[:16]
    r = Runner(stage="a17", mode="mock", results_dir=tmp_path / "raw", requests_dir=tmp_path / "req",
               backend=mock_backend("accept"), seed=2026)
    s = r.run(js)
    assert s["completed"] == 16 and s["missing"] == 0 and s["stopped"] is None
    lines = [json.loads(x) for x in r.path.read_text().splitlines() if '"type": "call"' in x]
    assert all(x["model"] == a17.MODEL_HAIKU and x["extra"]["a17"]["anthropic_requests"] for x in lines)


def test_haiku_thinking_blocks_kept_and_p6_check(tmp_path, monkeypatch):
    """Haiku's thinking blocks stay on its stored turn (upstream's Anthropic dialect); P6 counts them."""
    import litellm
    from src.runner.runner import Runner
    monkeypatch.setenv("A10_GUARD_DIR", str(tmp_path / "g"))
    blocks = [{"type": "thinking", "thinking": "", "signature": "sig-synthetic"}]

    def be(**kw):
        assert "anthropic" in kw["model"]
        return litellm.ModelResponse(model="claude-haiku-5-5", choices=[{"message": {
            "role": "assistant", "content": "", "thinking_blocks": blocks,
            "tool_calls": [{"id": "toolu_1", "type": "function", "function": {
                "name": "submit_verdict", "arguments": json.dumps({"reasoning": "synthetic", "verdict": "reject"})}}]},
            "finish_reason": "tool_calls"}], usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    res = a17.run(build_messages(OM[0], "R1", "omission"), "record_extraction", be, episode_id="t")
    asst = [m for m in res.messages_after if m.get("role") == "assistant"][-1]
    assert asst.get("thinking_blocks") == blocks and res.verdict == "reject"
    r = Runner(stage="a17", mode="mock", results_dir=tmp_path / "raw", requests_dir=tmp_path / "req", backend=be, seed=2026)
    r.run(L.p6_jobs())
    chk = L.p6_check(tmp_path / "raw")
    assert chk["calls"] == 10 and chk["submit_verdict_with_thinking"] == 10 and chk["passed"]
