"""Study 2 build: arms, branching, status line, guard, scheduler (mock model only; SYNTHETIC runs).

Mock runs execute src.hysteresis.run_arm in subprocesses (it changes the working directory and
monkeypatches upstream) with the deterministic mock model; no API call is possible (the guard
expects the mock's response model, and live mode refuses under pytest).
"""
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.hysteresis.analysis import status_line_check
from src.hysteresis.guard import JOURNAL, Budget, JournalLedger, Study2Stop, guarded_completion
from src.hysteresis.status_line import STATUS_LIMITED, STATUS_OPEN

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "data/raw/traces/communication/communication__gemini-3-1-flash-lite__unconstrained/rep001.json.gz"


def run_arm(*args, env=None):
    e = {**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}
    # PYTEST_CURRENT_TEST stays set: run_arm refuses live mode whenever it is present
    return subprocess.run([sys.executable, "-m", "src.hysteresis.run_arm", *map(str, args)], cwd=ROOT, env=e,
                          capture_output=True, text=True, timeout=600)


def only_run(d: Path) -> Path:
    runs = sorted(d.glob("*/run.json"))
    assert len(runs) == 1, runs
    return runs[0]


@pytest.fixture(scope="module")
def mock_seq(tmp_path_factory):
    """prefix, B, Aprime, Cprime for sequence 2 with the mock model."""
    root = tmp_path_factory.mktemp("s2")
    out = {}
    r = run_arm("--arm", "prefix", "--seq", 2, "--out-root", root, "--group", "t", "--backend", "mock")
    assert r.returncode == 0, r.stderr[-2000:]
    out["prefix"] = only_run(root / "t/rep002/prefix")
    for arm in ("B", "Aprime"):
        r = run_arm("--arm", arm, "--seq", 2, "--out-root", root, "--group", "t", "--backend", "mock",
                    "--resume-from", out["prefix"])
        assert r.returncode == 0, r.stderr[-2000:]
        out[arm] = only_run(root / f"t/rep002/{arm}")
    r = run_arm("--arm", "Cprime", "--seq", 2, "--out-root", root, "--group", "t", "--backend", "mock")
    assert r.returncode == 0, r.stderr[-2000:]
    out["Cprime"] = only_run(root / "t/rep002/Cprime")
    out["root"] = root
    return out


def load(p):
    return json.loads(Path(p).read_text())


def test_episode_counts_and_channel_states(mock_seq):
    want = {"prefix": [True] * 5, "Aprime": [True] * 10, "B": [True] * 5 + [False] * 5, "Cprime": [False] * 10}
    for arm, flags in want.items():
        r = load(mock_seq[arm])
        assert [e["throttled"] for e in r["results"]] == flags, arm
        assert [e["episode_index"] for e in r["results"]] == list(range(len(flags)))


def test_branches_copy_the_prefix_unchanged(mock_seq):
    p = load(mock_seq["prefix"])["results"]
    for arm in ("B", "Aprime"):
        assert load(mock_seq[arm])["results"][:5] == p, arm
    # the prefix run.json was not modified by the branches (sha recorded at branch start)
    import hashlib
    sha = hashlib.sha256(Path(mock_seq["prefix"]).read_bytes()).hexdigest()
    for arm in ("B", "Aprime"):
        assert load(mock_seq[arm].parent / "study2_meta.json")["resume_from_sha256"] == sha


@pytest.mark.skipif(not TRACE.exists(), reason="published traces not downloaded")
def test_settings_match_shi_et_al(mock_seq):
    shi = json.load(gzip.open(TRACE, "rt"))["run_config"]
    for arm in ("prefix", "B", "Aprime", "Cprime"):
        rc = load(mock_seq[arm])["run_config"]
        for k in ("models", "llm_request_parameters", "reasoning_efforts", "max_rounds", "char_limit",
                  "memory_scope", "cross_episode_memory_scope", "cross_episode_memory_length", "verdict_policy",
                  "reflection", "reward", "verdict_review", "verdict_evaluation", "reward_scheme", "reward_scope",
                  "reward_type", "task_attempts", "communication_attempts", "verdict_attempts", "tool_choice_mode",
                  "litellm_version"):
            assert rc[k] == shi[k], (arm, k)
        assert rc["prompt_texts"]["system_prompts"] == shi["prompt_texts"]["system_prompts"], arm
        assert rc["manifest"].endswith("task/task_sequences_50x10/rep002_sampled_manifest.json")


def test_status_line_from_episode_6_only(mock_seq):
    runs = [(2, arm, load(mock_seq[arm])) for arm in ("prefix", "B", "Aprime", "Cprime")]
    table, ok = status_line_check(runs)
    assert ok, table[table.get("ok", True) == False].to_string() if hasattr(table, "to_string") else table
    for arm, text, other in (("B", STATUS_OPEN, STATUS_LIMITED), ("Cprime", STATUS_OPEN, STATUS_LIMITED),
                             ("Aprime", STATUS_LIMITED, STATUS_OPEN)):
        for e in load(mock_seq[arm])["results"]:
            for a in ("alice", "bob"):
                jp = e["agents"][a]["judging_prompt"]
                if e["episode_index"] >= 5:
                    assert jp.endswith("\n\n" + text) and jp.count(text) == 1 and other not in jp
                else:
                    assert text not in jp and other not in jp


def test_journal_name_matches_upstream():
    import src.upstream  # noqa: F401
    from experiments.usage import LLM_USAGE_JOURNAL_FILENAME
    assert JOURNAL == LLM_USAGE_JOURNAL_FILENAME


def _journal(path: Path, n: int, tokens: int = 1_000_000, torn: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"requested_model": "gemini/gemini-3.1-flash-lite", "input_tokens": tokens, "cached_input_tokens": 0,
           "billable_output_tokens": 0}
    with open(path, "a") as fh:
        for _ in range(n):
            fh.write(json.dumps(rec) + "\n")
        if torn:
            fh.write('{"requested_model": "gemini/gem')


def test_ledger_prices_and_ignores_torn_line(tmp_path):
    _journal(tmp_path / "p8/rep001/B/run_x" / JOURNAL, 2, torn=True)
    led = JournalLedger(tmp_path).refresh()
    assert led.total == pytest.approx(0.5)            # 2 x 1M uncached input x 0.25 USD/M
    assert led.by_group() == {"p8": pytest.approx(0.5)}
    _journal(tmp_path / "main/rep001/B/run_y" / JOURNAL, 4)
    assert led.refresh().by_group()["main"] == pytest.approx(1.0)


CAPS = {"hard_cap_usd": 3.0, "stages": {"study2": 2.0},
        "check_groups": {"study2_p8": {"stage": "study2", "checks": ["P8"], "cap_usd": 0.6}}}


def test_budget_caps_fail_closed(tmp_path):
    _journal(tmp_path / "p8/a" / JOURNAL, 2)                       # 0.5 spent in p8
    Budget(root=tmp_path, group="p8", caps=CAPS, project_results=None).check(0.05)
    with pytest.raises(Study2Stop, match="group p8"):
        Budget(root=tmp_path, group="p8", caps=CAPS, project_results=None).check(0.2)
    _journal(tmp_path / "main/a" / JOURNAL, 6)                     # +1.5 -> 2.0 study2
    with pytest.raises(Study2Stop, match="stage study2"):
        Budget(root=tmp_path, group="main", caps=CAPS, project_results=None).check(0.01)
    with pytest.raises(Study2Stop, match="no cap configured"):
        Budget(root=tmp_path, group="main", caps={"hard_cap_usd": 9, "stages": {}}, project_results=None).check(0)


def test_budget_hard_cap_counts_other_stages(tmp_path):
    proj = tmp_path / "raw"
    proj.mkdir()
    (proj / "x.jsonl").write_text(json.dumps({"type": "call", "mode": "live", "stage": "main", "cost_usd": 2.9}) + "\n")
    s2 = tmp_path / "s2"
    _journal(s2 / "main/a" / JOURNAL, 1)                            # 0.25
    with pytest.raises(Study2Stop, match="hard cap"):
        Budget(root=s2, group="main", caps={**CAPS, "stages": {"study2": 9}}, project_results=proj).check(0.0)


def test_stop_is_not_an_exception():
    assert not issubclass(Study2Stop, Exception)   # upstream retries every Exception


def test_guard_model_change_writes_stop(tmp_path):
    class R:
        model = "gemini-3.2-flash-lite"
    budget = Budget(root=tmp_path, group="main", caps={"hard_cap_usd": 9, "stages": {"study2": 9}},
                    project_results=None)
    stop = tmp_path / "STOP"
    g = guarded_completion(lambda **kw: R(), budget=budget, reserve_usd=0, expected_model="gemini-3.1-flash-lite",
                           stop_file=stop)
    with pytest.raises(Study2Stop, match="response_model"):
        g(messages=[])
    assert stop.exists()
    with pytest.raises(Study2Stop, match="STOP file"):
        g(messages=[])


def test_cap_stop_ends_a_mock_run(tmp_path):
    caps = tmp_path / "caps.json"
    caps.write_text(json.dumps({"hard_cap_usd": 100, "stages": {"study2": 0.02}}))
    r = run_arm("--arm", "Cprime", "--seq", 1, "--out-root", tmp_path / "o", "--group", "t", "--backend", "mock",
                "--caps-json", caps)
    assert r.returncode != 0 and "Study2Stop" in r.stderr
    meta = load(next((tmp_path / "o/t/rep001/Cprime").glob("*/study2_meta.json")))
    assert meta["status"].startswith("failed: Study2Stop") and meta["episodes"] < 10


def test_live_refused_without_authorization(tmp_path):
    r = run_arm("--arm", "prefix", "--seq", 1, "--out-root", tmp_path, "--group", "t", "--backend", "live")
    assert r.returncode != 0 and "LiveNotAuthorized" in r.stderr
    assert not list(tmp_path.rglob(JOURNAL))


def test_resume_sends_identical_requests(tmp_path):
    """Episodes 6-10 resumed from an episode-5 run.json send byte-identical requests to an
    uninterrupted run (deterministic mock): branching adds no context difference vs. C'."""
    cont, res = tmp_path / "cont.jsonl", tmp_path / "res.jsonl"
    r = run_arm("--arm", "Cprime", "--seq", 4, "--out-root", tmp_path / "o", "--group", "c", "--backend", "mock",
                env={"STUDY2_MOCK_REQUEST_LOG": str(cont)})
    assert r.returncode == 0, r.stderr[-2000:]
    rec = load(only_run(tmp_path / "o/c/rep004/Cprime"))
    rec["results"] = rec["results"][:5]
    (tmp_path / "t5.json").write_text(json.dumps(rec))
    r = run_arm("--arm", "Cprime", "--seq", 4, "--out-root", tmp_path / "o", "--group", "r", "--backend", "mock",
                "--resume-from", tmp_path / "t5.json", env={"STUDY2_MOCK_REQUEST_LOG": str(res)})
    assert r.returncode == 0, r.stderr[-2000:]
    a = [json.loads(x)["hash"] for x in cont.read_text().splitlines()]
    b = [json.loads(x)["hash"] for x in res.read_text().splitlines()]
    assert len(b) > 0 and b == a[len(a) - len(b):]
    assert load(only_run(tmp_path / "o/r/rep004/Cprime"))["results"] == load(only_run(tmp_path / "o/c/rep004/Cprime"))["results"]


def test_fix_n_rule():
    from scripts.study2.fix_n import decide
    # 4.0 USD/seq -> 4.6 with reserve; 250 - 4 remaining -> 50 fits (230)
    assert decide(4.0, 4.0, 250, 20, 330)["n"] == 50
    # 5.5 -> 6.325: 50 -> 316 no, 40 -> 253 > 244.5 no, 30 -> 189.75 yes
    assert decide(5.5, 5.5, 250, 20, 330)["n"] == 30
    # hard cap binds: 330 - 120 - 4 = 206 < 230 -> 40 (184)
    assert decide(4.0, 4.0, 250, 120, 330)["n"] == 40
    d = decide(9.0, 9.0, 250, 20, 330)    # 10.35 x 30 = 310.5 > 241 -> dropped
    assert d["n"] is None and d["dropped"] and d["sequences"] == []
    assert decide(4.0, 4.0, 250, 20, 330)["sequences"][:2] == ["rep001", "rep002"]


def test_scheduler_one_sequence_order_and_status_line(tmp_path):
    """Mock: all five arms of one sequence via the scheduler; PC launches only after B exits."""
    from src.hysteresis.scheduler import EXPECTED, Scheduler, scan
    s = Scheduler(out_root=tmp_path, group="t", seqs=[5], workers=8, backend="mock", log_dir=tmp_path / "logs",
                  poll_s=0.5)
    result = s.run()
    assert result["done"] == 5 and not result["failed"]
    ev = [json.loads(x) for x in (tmp_path / "t/scheduler.jsonl").read_text().splitlines()]
    pos = {(e["event"], e.get("arm")): i for i, e in enumerate(ev)}
    assert pos[("exit", "B")] < pos[("launch", "PC")]
    assert pos[("exit", "prefix")] < min(pos[("launch", "B")], pos[("launch", "Aprime")])
    runs = [(5, a, load(scan(tmp_path / "t", 5, a).complete_run())) for a in EXPECTED]
    assert status_line_check(runs)[1]


def test_counted_run_is_earliest_complete(tmp_path):
    from src.hysteresis.scheduler import scan
    for name, started, eps in (("r1", "2026-10-24T12:00:00", 10), ("r2", "2026-10-24T11:00:00", 10),
                               ("r3", "2026-10-24T10:00:00", 4)):
        d = tmp_path / "g/rep001/B" / name
        d.mkdir(parents=True)
        (d / "study2_meta.json").write_text(json.dumps({"started_at": started, "status": "complete"}))
        (d / "run.json").write_text(json.dumps({"results": [{}] * eps}))
    st = scan(tmp_path / "g", 1, "B")
    assert st.complete and st.complete_run().parent.name == "r2" and st.attempts == 3


def test_failed_launches_count_as_attempts(tmp_path):
    """A launch that dies before writing study2_meta.json (here: live refused, no API call) still
    counts toward MAX_ATTEMPTS, so the scheduler does not relaunch it forever."""
    from src.hysteresis.scheduler import MAX_ATTEMPTS, Scheduler
    s = Scheduler(out_root=tmp_path, group="t", seqs=[1], workers=2, backend="live", approved_stage=None,
                  log_dir=tmp_path / "logs", poll_s=0.5)
    result = s.run()
    ev = [json.loads(x) for x in (tmp_path / "t/scheduler.jsonl").read_text().splitlines()]
    n = {}
    for e in ev:
        if e["event"] == "launch":
            n[e["arm"]] = n.get(e["arm"], 0) + 1
    assert n == {"prefix": MAX_ATTEMPTS, "Cprime": MAX_ATTEMPTS}
    assert sorted(map(tuple, result["failed"])) == [(1, "Cprime"), (1, "prefix")]
    assert not list(tmp_path.rglob(JOURNAL))


def test_attempts_reset_event(tmp_path):
    from src.hysteresis.scheduler import Scheduler
    s = Scheduler(out_root=tmp_path, group="t", seqs=[1], workers=1, backend="mock", log_dir=tmp_path / "l")
    for _ in range(4):
        s.log(event="launch", seq=1, arm="B", pid=1)
    assert s.launches() == {(1, "B"): 4}
    s.log(event="attempts_reset", reason="test")
    s.log(event="launch", seq=1, arm="B", pid=2)
    assert s.launches() == {(1, "B"): 1}
