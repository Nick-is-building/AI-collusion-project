"""A05b: superseding move, stop watcher, scheduler watcher gate, sensitivities (SYNTHETIC data only)."""
import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from scripts.study2 import stop_watch as SW
from scripts.study2.supersede import supersede
from src.hysteresis import sensitivity_a05b as S
from src.hysteresis.scheduler import Scheduler, scan


def _run(gdir, seq, arm, name, episodes, started="2026-10-24T15:00:00+00:00", status="complete"):
    d = gdir / f"rep{seq:03d}" / arm / name
    d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps({"results": [{"episode_index": i} for i in range(episodes)]}))
    (d / "study2_meta.json").write_text(json.dumps({"status": status, "started_at": started, "pid": None}))
    return d


def test_supersede_moves_keeps_paths_and_logs(tmp_path):
    g = tmp_path / "main"
    _run(g, 14, "Cprime", "run_a", 4)
    _run(g, 14, "Cprime", "run_b", 0)
    _run(g, 14, "B", "run_c", 10)
    _run(g, 46, "Cprime", "run_d", 10)
    (g / "scheduler.jsonl").write_text('{"at": "x", "event": "launch"}\n')
    before = (g / "scheduler.jsonl").read_text()
    r = supersede(tmp_path, "main", "main_superseded", [14, 15], "Cprime", "test", check_processes=False)
    assert r["n"] == 2
    assert (tmp_path / "main_superseded/rep014/Cprime/run_a/run.json").exists()
    assert not list((g / "rep014/Cprime").iterdir())
    assert (g / "rep014/B/run_c").exists() and (g / "rep046/Cprime/run_d").exists()
    log = (g / "scheduler.jsonl").read_text()
    assert log.startswith(before) and json.loads(log.splitlines()[-1])["event"] == "superseded_moved"
    _run(g, 14, "Cprime", "run_a", 1)          # clash with an existing destination: refused
    with pytest.raises(SystemExit):
        supersede(tmp_path, "main", "main_superseded", [14], "Cprime", "test", check_processes=False)


def test_after_supersede_cprime_starts_fresh_with_reset(tmp_path):
    g = tmp_path / "main"
    _run(g, 14, "prefix", "p", 5)
    _run(g, 14, "Cprime", "old", 4, status="failed: x")
    s = Scheduler(out_root=tmp_path, group="main", seqs=[14], workers=1, backend="mock", log_dir=tmp_path / "logs")
    for _ in range(3):
        s.log(event="launch", seq=14, arm="Cprime", pid=1)
    st = s.state()
    assert "--resume-from" in s.command(st[(14, "Cprime")], st)   # before: resumes the partial run
    supersede(tmp_path, "main", "main_superseded", [14], "Cprime", "test", check_processes=False)
    st = s.state()
    assert st[(14, "Cprime")].runs == []
    assert "--resume-from" not in s.command(st[(14, "Cprime")], st)  # after: fresh, episodes 1-10
    assert s.attempts(st[(14, "Cprime")]) == 3
    s.log(event="attempts_reset", reason="test")
    assert s.attempts(st[(14, "Cprime")]) == 0


def test_scheduler_requires_live_watcher(tmp_path):
    s = Scheduler(out_root=tmp_path, group="main", seqs=[1], workers=1, backend="mock", log_dir=tmp_path / "logs",
                  require_stop_watch=True)
    assert s.stopped()
    assert '"stop_watch_missing"' in (tmp_path / "main/scheduler.jsonl").read_text()
    s2 = Scheduler(out_root=tmp_path, group="main", seqs=[1], workers=1, backend="mock", log_dir=tmp_path / "logs")
    assert not s2.stopped()


def _journal(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def _err(at, msg="You exceeded your current quota", code=429):
    return {"recorded_at": at.isoformat(), "error_category": "transient_rate_limit",
            "error_message": f'{{"error": {{"code": {code}, "message": "{msg}"}}}}', "response_status": "error_retryable"}


def _watch(tmp_path):
    return SW.StopWatch(out_root=tmp_path, group="main", log_dir=tmp_path / "logs")


def test_watch_ignores_old_content_then_stops_on_spending_cap_log(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.log").write_text("429 Your project has exceeded its monthly spending cap.\n")
    _journal(tmp_path / "main/rep001/B/r/llm_usage.jsonl",
             [_err(datetime.now(timezone.utc) - timedelta(hours=20), "monthly spending cap")] * 30)
    w = _watch(tmp_path)
    assert w.check() is None and w.n_429 == 0
    with open(logs / "old.log", "a") as fh:
        fh.write("retry 1/20 ... exceeded its monthly Spending Cap ...\n")
    reason = w.check()
    assert reason and "spending cap" in reason
    w.stop(reason)
    assert (tmp_path / "STOP").exists()
    assert json.loads((tmp_path / "main/stop_watch.json").read_text())["state"] == "stopped"
    assert "stop_watch_stop" in (tmp_path / "main/scheduler.jsonl").read_text()


def test_watch_new_log_file_spending_cap(tmp_path):
    (tmp_path / "logs").mkdir()
    w = _watch(tmp_path)
    (tmp_path / "logs/rep014_Cprime.log").write_text("ok\nexceeded its monthly spending cap\n")
    assert "spending cap" in w.check()


def test_watch_quota_429_window(tmp_path):
    (tmp_path / "logs").mkdir()
    w = _watch(tmp_path)
    j = tmp_path / "main/rep014/Cprime/r/llm_usage.jsonl"
    now = datetime.now(timezone.utc)
    _journal(j, [_err(now)] * 10)                     # exactly 10: upstream keeps retrying
    assert w.check() is None and w.n_429 == 10
    _journal(j, [{"recorded_at": now.isoformat(), "response_status": "accepted"}])
    assert w.check() is None
    _journal(j, [_err(now)])                          # the 11th within 5 minutes: stop
    assert "11 quota 429s" in w.check()


def test_watch_429s_outside_window_do_not_add_up(tmp_path):
    (tmp_path / "logs").mkdir()
    w = _watch(tmp_path)
    w.started = datetime.now(timezone.utc) - timedelta(minutes=30)
    j = tmp_path / "main/rep014/Cprime/r/llm_usage.jsonl"
    now = datetime.now(timezone.utc)
    _journal(j, [_err(now - timedelta(minutes=20))] * 8 + [_err(now)] * 8)
    assert w.check() is None


def test_watcher_alive_false_for_dead_pid(tmp_path):
    p = tmp_path / "stop_watch.json"
    p.write_text(json.dumps({"pid": 999999999}))
    assert not SW.watcher_alive(p)
    assert not SW.watcher_alive(tmp_path / "missing.json")


def _rows(cp_shift=0.0):
    rng = np.random.default_rng(0)
    out = []
    for seq in range(1, 51):
        for arm, base in (("B", 0.4), ("Cprime", 0.6 + (cp_shift if seq in S.RERUN_SEQS else 0.0))):
            for ep in (5, 6, 7):
                for judge in ("alice", "bob"):
                    out.append({"seq": seq, "arm": arm, "episode_index": ep, "judge": judge,
                                "strict_full": bool(rng.random() < base)})
    return pd.DataFrame(out)


def test_sensitivity_groups_and_values():
    assert len(S.RERUN_SEQS) == 32 and len(S.NOT_RERUN_SEQS) == 18
    assert not set(S.RERUN_SEQS) & set(S.NOT_RERUN_SEQS)
    rows = _rows()
    p1 = S.primary_not_rerun(rows)
    assert p1["n"] == 18 and p1["n_excluded"] == 0
    c = rows[rows.seq.isin(S.NOT_RERUN_SEQS)]
    exp = (c[c.arm == "B"].groupby("seq").strict_full.mean() - c[c.arm == "Cprime"].groupby("seq").strict_full.mean()).mean()
    assert p1["mean_d"] == pytest.approx(exp)
    d = S.cprime_drift_rerun_vs_original(_rows(cp_shift=-0.4))
    assert d["n_rerun"] == 32 and d["n_original"] == 18
    assert d["diff_rerun_minus_original"] < 0 and d["ci95_bootstrap"]["hi"] < 0


def test_two_group_bootstrap_null_covers_zero():
    rng = np.random.default_rng(1)
    ci = S.two_group_bootstrap(rng.normal(0, 1, 32), rng.normal(0, 1, 18))
    assert ci["lo"] < 0 < ci["hi"]


def test_launch_lags_use_counted_runs(tmp_path):
    g = tmp_path / "main"
    _run(g, 14, "B", "b", 10, started="2026-10-24T14:00:00+00:00")
    _run(g, 14, "Cprime", "c_fail", 3, started="2026-10-24T15:00:00+00:00", status="failed: x")
    _run(g, 14, "Cprime", "c", 10, started="2026-10-25T10:00:00+00:00")
    _run(g, 1, "B", "b1", 10, started="2026-10-24T13:30:00+00:00")
    lags = S.launch_lags(g, [1, 14])
    assert lags.set_index("seq").loc[14, "lag_min_Cprime_minus_B"] == pytest.approx(20 * 60)
    assert pd.isna(lags.set_index("seq").loc[1, "lag_min_Cprime_minus_B"])
    s = S.lag_summary(lags)
    assert s["rerun"]["n"] == 1 and s["not_rerun"]["n"] == 0
