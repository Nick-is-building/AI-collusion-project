"""Offline tests of src/replay/token_count.py (no network; live counts are refused under pytest)."""
import json

import pytest

from src.replay.token_count import count_tokens, count_url, http_body, request_kwargs
from src.replay.variants import build, load_item


def _body(variant="R0"):
    msgs = build(load_item("rep002.json.gz", 2), variant)
    return msgs, http_body(request_kwargs(msgs, "record_extraction"))


def test_http_body_is_litellm_generate_content_request():
    msgs, (url, body) = _body()
    assert url.endswith("/models/gemini-3.1-flash-lite:generateContent")
    assert count_url(url).endswith(":countTokens")
    assert {"contents", "system_instruction", "tools", "toolConfig", "generationConfig"} <= set(body)
    names = [t["name"] for t in body["tools"][0]["function_declarations"]]
    assert names == ["submit_verdict"]
    # the system prompt is sent as system_instruction, the rest as contents
    assert body["system_instruction"]["parts"][0]["text"] == msgs[0]["content"]


def test_http_body_keeps_null_record_ids():
    # the A03 R0 mismatch cause: stored {"record_id": null} items are sent unchanged by LiteLLM
    msgs = build(load_item("rep003.json.gz", 1, "bob"), "R0")
    _, body = http_body(request_kwargs(msgs, "record_extraction", judge="bob"))
    assert '"record_id": null' in json.dumps(body)


def test_count_tokens_guards():
    _, (url, body) = _body("R4")
    with pytest.raises(PermissionError):
        count_tokens(body, url, purpose="anything_else")
    body = dict(body, _test_nonce="not-in-cache")
    with pytest.raises(RuntimeError):
        count_tokens(body, url, purpose="r5_filler", live=False)
    with pytest.raises(PermissionError):
        count_tokens(body, url, purpose="r5_filler", live=True)
