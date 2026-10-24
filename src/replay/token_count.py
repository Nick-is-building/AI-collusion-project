"""Exact Gemini request bodies (offline) and the free countTokens endpoint (assignment A03).

`request_kwargs` runs Shi et al.'s verdict path (`src.replay.request.run_verdict`) with a capturing
mock backend, so the completion kwargs are exactly what a live replay call would pass to LiteLLM.

`http_body` passes those kwargs to `litellm.completion` with a fake HTTP client that records the
JSON body LiteLLM 1.94.1 would POST to Google and then aborts: no network. The body is the
generateContent request (contents, system_instruction, tools, toolConfig, generationConfig).

`count_tokens` POSTs `{"generateContentRequest": {"model": ..., **body}}` to the countTokens method
of the same API version LiteLLM uses for generateContent (v1alpha). countTokens is free and not
billable. A03 authorizes it for two purposes only: the R0 token bisection (task 1) and R5 filler
matching (task 3); `purpose` must name one of them. Every live count is appended to
`results/token_counts/counts.jsonl` (one line per call, flushed) and reused from there by body hash,
so a restart never repeats a count. The API key is read from the environment and never logged.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
from pathlib import Path

import src.upstream  # noqa: F401
import litellm
from litellm.llms.custom_httpx.http_handler import HTTPHandler

from src.replay.request import MODEL, canonical_json, mock_backend, run_verdict, sha256_text

ROOT = Path(__file__).resolve().parents[2]
COUNT_LOG = ROOT / "results" / "token_counts" / "counts.jsonl"
AUTHORIZED_PURPOSES = ("r0_bisection", "r5_filler", "r5post_filler")   # r5post_filler: D26 (A06) token matching
API_BASE = "https://generativelanguage.googleapis.com"


class _Captured(Exception):
    pass


class _CaptureClient(HTTPHandler):
    def post(self, url, data=None, json=None, headers=None, **kw):  # noqa: A002
        self.captured = dict(url=str(url).split("?")[0], data=data, json=json)
        raise _Captured()


def request_kwargs(messages: list, task_type: str, *, judge: str = "alice", model: str = MODEL,
                   tools_override=None) -> dict:
    """Completion kwargs of the first verdict attempt, built by upstream code; no network."""
    reqs: list = []

    def be(**kw):
        reqs.append(copy.deepcopy(kw))
        return mock_backend()(**kw)

    run_verdict(messages, task_type, be, judge=judge, model=model)
    kw = reqs[0]
    if tools_override is not None:
        kw["tools"] = tools_override
    return kw


def http_body(kwargs: dict) -> tuple[str, dict]:
    """(generateContent URL without key, JSON body) that LiteLLM would send; no network."""
    c = _CaptureClient()
    try:
        litellm.completion(**copy.deepcopy(kwargs), client=c, api_key="offline-capture")
    except Exception:  # noqa: BLE001  (LiteLLM wraps _Captured in its own error type)
        pass
    cap = getattr(c, "captured", None)
    if cap is None:
        raise RuntimeError("LiteLLM did not reach the HTTP layer")
    body = cap["json"] if cap["json"] is not None else json.loads(cap["data"])
    return cap["url"], body


def count_url(generate_url: str) -> str:
    assert generate_url.endswith(":generateContent"), generate_url
    return generate_url[: -len(":generateContent")] + ":countTokens"


def _cached() -> dict:
    out = {}
    if COUNT_LOG.exists():
        for line in COUNT_LOG.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("total_tokens") is not None:
                out[r["body_sha256"]] = r["total_tokens"]
    return out


_CACHE: dict | None = None


def count_tokens(body: dict, generate_url: str, *, purpose: str, label: str = "", live: bool = False,
                 timeout: float = 60.0) -> int:
    """totalTokens for a generateContent body. Cached by body hash; live call only with live=True."""
    global _CACHE
    if purpose not in AUTHORIZED_PURPOSES:
        raise PermissionError(f"countTokens purpose {purpose!r} not authorized (A03: {AUTHORIZED_PURPOSES})")
    h = sha256_text(canonical_json(body))
    if _CACHE is None:
        _CACHE = _cached()
    if h in _CACHE:
        return _CACHE[h]
    if not live:
        raise RuntimeError("count not cached and live=False")
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise PermissionError("live countTokens disabled under pytest")
    import httpx

    model_name = generate_url.rsplit("/models/", 1)[1].split(":")[0]
    req = {"generateContentRequest": {"model": f"models/{model_name}", **body}}
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    t0 = dt.datetime.now(dt.timezone.utc).isoformat()
    r = httpx.post(count_url(generate_url), json=req, headers={"x-goog-api-key": key}, timeout=timeout)
    rec = dict(ts_utc=t0, purpose=purpose, label=label, body_sha256=h, url=count_url(generate_url),
               http_status=r.status_code, litellm_version=litellm.__version__ if hasattr(litellm, "__version__")
               else None)
    if r.status_code == 200:
        j = r.json()
        rec["total_tokens"] = j.get("totalTokens")
        rec["response"] = j
    else:
        rec["total_tokens"] = None
        rec["error"] = r.text[:2000]
    COUNT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(COUNT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    if rec["total_tokens"] is None:
        raise RuntimeError(f"countTokens HTTP {r.status_code}: {rec['error'][:300]}")
    _CACHE[h] = rec["total_tokens"]
    return rec["total_tokens"]
