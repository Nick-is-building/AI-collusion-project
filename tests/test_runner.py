"""Runner: append-only JSONL, resume, response_model stop, fail-closed caps, missing verdicts,
retry override, live refusal. Mock backends only; files only under scratch/."""
import json
import shutil
import uuid
from pathlib import Path

import litellm
import pytest

import experiments.agents as up_agents
from src.replay.request import mock_backend
from src.runner.costs import CapExceeded, Ledger, PriceTable
from src.runner.runner import Job, LiveNotAuthorized, Runner

ROOT = Path(__file__).resolve().parents[1]
CAPS = {"hard_cap_usd": 250.0, "stages": {"pilot": 10.0}}
MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "## Episode 2: verdict phase\n\nJudge."}]


@pytest.fixture
def sdir():
    d = ROOT / "scratch" / "pytest" / f"runner-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def jobs(n, model="gemini/gemini-3.1-flash-lite", **kw):
    return [Job(check="T", item_id=f"it{i}", variant="R0", version="correct", draw=1, judge="alice",
                task_type="data_search", build_messages=lambda: [dict(m) for m in MSGS], est_input_tokens=1000,
                model=model, **kw) for i in range(n)]


def runner(sdir, backend, caps=CAPS, **kw):
    return Runner(stage="pilot", mode="mock", results_dir=sdir / "raw", requests_dir=sdir / "req",
                  backend=backend, caps=caps, seed=2026, log=lambda *a: None, **kw)


def lines(sdir):
    out = []
    for f in sorted((sdir / "raw").glob("*.jsonl")):
        out += [json.loads(l) for l in f.read_text().splitlines()]
    return out


class Kill(BaseException):
    pass


def counting(backend, kill_after=None, models=None):
    state = {"n": 0}

    def b(**kw):
        state["n"] += 1
        if kill_after is not None and state["n"] > kill_after:
            raise Kill()
        r = backend(**kw)
        if models:
            r.model = models[min(state["n"], len(models)) - 1]
        return r
    b.state = state
    return b


def test_lines_provenance_and_requests(sdir):
    st = runner(sdir, mock_backend("accept", input_tokens=1000)).run(jobs(3))
    assert st["completed"] == 3 and st["stopped"] is None
    recs = lines(sdir)
    assert [r["type"] for r in recs] == ["run_start", "call", "call", "call", "run_end"]
    c = recs[1]
    for k in ("run_id", "git_commit", "litellm_version", "upstream_commit", "seed", "ts_start_utc",
              "request_sha256", "response_models", "usage", "verdict", "reasoning", "forced", "cost_usd"):
        assert k in c
    assert c["call_id"] == "pilot:T:it0:R0:correct:1" and c["verdict"] == "accept" and c["verdict_status"] == "ok"
    assert c["litellm_version"] == "1.94.1" and c["seed"] == 2026
    assert c["cost_usd"] == pytest.approx((1000 * 0.25 + 10 * 1.50) / 1e6)
    assert (sdir / "req" / c["run_id"] / f"{c['request_sha256'][0]}.json.gz").exists()


def test_resume_after_kill_no_duplicates(sdir):
    b = counting(mock_backend("accept"), kill_after=2)
    with pytest.raises(Kill):
        runner(sdir, b).run(jobs(5))
    assert sum(r["type"] == "call" for r in lines(sdir)) == 2
    st = runner(sdir, mock_backend("accept")).run(jobs(5))
    assert st["completed"] == 3
    calls = [r for r in lines(sdir) if r["type"] == "call"]
    assert len(calls) == 5 and len({c["call_id"] for c in calls}) == 5
    assert len({c["run_id"] for c in calls}) == 2 and len(list((sdir / "raw").glob("*.jsonl"))) == 2
    assert runner(sdir, mock_backend("accept")).run(jobs(5))["completed"] == 0


def test_response_model_change_stops(sdir):
    b = counting(mock_backend("accept"), models=["m-a", "m-b"])
    st = runner(sdir, b).run(jobs(4))
    assert st["stopped"].startswith("ModelChanged") and st["completed"] == 2 and b.state["n"] == 2
    # a later run sees the change against the first observed value too
    st = runner(sdir, counting(mock_backend("accept"), models=["m-b"])).run(jobs(4))
    assert st["stopped"].startswith("ModelChanged") and st["completed"] == 1


def test_cap_fail_closed_before_call(sdir):
    b = counting(mock_backend("accept"))
    st = runner(sdir, b, caps={"hard_cap_usd": 250.0, "stages": {"pilot": 1e-6}}).run(jobs(2))
    assert st["stopped"].startswith("CapExceeded") and b.state["n"] == 0
    b = counting(mock_backend("accept"))
    st = runner(sdir, b, caps={"hard_cap_usd": 1e-6, "stages": {"pilot": 10.0}}).run(jobs(2))
    assert st["stopped"].startswith("CapExceeded") and b.state["n"] == 0
    st = runner(sdir, b, caps={"hard_cap_usd": 250.0, "stages": {}}).run(jobs(1))
    assert st["stopped"].startswith("CapExceeded")


def test_ledger_spend_counts_toward_cap(sdir):
    runner(sdir, mock_backend("accept", input_tokens=100000)).run(jobs(2))
    led = Ledger(sdir / "raw", "mock")
    assert led.total == pytest.approx(2 * (100000 * 0.25 + 10 * 1.5) / 1e6)
    with pytest.raises(CapExceeded):
        led.check("pilot", 0.01, {"hard_cap_usd": led.total + 0.005, "stages": {"pilot": 10}})


def test_unpriced_model_refused(sdir):
    b = counting(mock_backend("accept"))
    st = runner(sdir, b).run(jobs(1, model="gemini/gemini-3.7-flash"))
    assert st["stopped"].startswith("UnpricedModel") and b.state["n"] == 0
    st = runner(sdir, b).run(jobs(1, model="gemini/gemini-3.7-flash", allow_undocumented_price=True))
    assert st["completed"] == 1


def test_missing_verdicts(sdir):
    st = runner(sdir, mock_backend("reject", fail_first=3)).run(jobs(1))
    c = [r for r in lines(sdir) if r["type"] == "call"][0]
    assert c["forced"] is True and c["verdict_status"] == "missing_forced" and c["n_api_requests"] == 3

    def auth_error(**kw):
        raise litellm.exceptions.AuthenticationError("no key", llm_provider="gemini", model=kw["model"])
    second = [j for j in jobs(2)][1:]
    st = runner(sdir, auth_error).run(second)
    # select by call_id: run files from the same second can sort in either order
    c = [r for r in lines(sdir) if r["type"] == "call" and r["call_id"] == second[0].call_id("pilot")][0]
    assert st["missing"] == 1 and c["status"] == "missing" and c["verdict_status"] == "missing_error"
    assert "AuthenticationError" in c["error"]


def test_retry_override_to_plan_value(sdir):
    seen = []

    def b(**kw):
        seen.append(up_agents.LLM_MAX_RETRIES)
        return mock_backend("accept")(**kw)
    before = up_agents.LLM_MAX_RETRIES
    runner(sdir, b).run(jobs(1))
    assert seen == [5] and up_agents.LLM_MAX_RETRIES == before == 20


def test_live_refused(sdir):
    with pytest.raises(LiveNotAuthorized):
        Runner(stage="pilot", mode="live", results_dir=sdir / "raw", requests_dir=sdir / "req",
               approved_stage="pilot")
    with pytest.raises(LiveNotAuthorized):
        Runner(stage="pilot", mode="live", results_dir=sdir / "raw", requests_dir=sdir / "req")


def test_prices():
    p = PriceTable()
    assert p.cost("gemini/gemini-3.1-flash-lite", 1_000_000, 0, 1_000_000) == pytest.approx(1.75)
    assert p.cost("gemini/gemini-3.1-flash-lite", 1_000_000, 1_000_000, 0) == pytest.approx(0.025)
    assert p.cost("anthropic/claude-haiku-5-5", 100_000, 0, 0) == pytest.approx(0.01)
    assert p.cost("anthropic/claude-haiku-5-5", 100_001, 0, 0) == pytest.approx(100_001 * 0.5 / 1e6)
    assert not p.documented("gemini/gemini-3.7-flash")
