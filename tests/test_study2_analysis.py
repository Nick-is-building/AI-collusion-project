"""Tests for src/hysteresis/analysis.py and scripts/study2/analyze.py.

All run dicts built here are SYNTHETIC (labelled synth_*); they carry only the fields the analysis
reads, with realistic raw logs and channel messages so that strict_full is genuinely computed by
src.reanalysis.transmission. Check A runs on Shi et al.'s published traces (skipped if absent).
"""
from __future__ import annotations

import gzip
import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from scripts.study2 import analyze as cli
from src.hysteresis import analysis as A
from src.replay.traces import CONDITION, TRACE_DIR

PAIRS = [(e, s) for e in A.EVAL_EPS for s in ("alice", "bob")]  # (episode_index, sender)


# ---------------------------------------------------------------- SYNTHETIC run builder
def synth_raw_log(seq, arm, ep, agent):
    """SYNTHETIC private_raw_log in upstream's list-of-tool-calls shape."""
    return [{"seq": 1, "tool": "inspect_database", "arguments": {},
             "result": {"success": True, "tables": [f"t_{seq}_{arm}_{ep}_{agent}", "vendors", "departments"]}},
            {"seq": 2, "tool": "query_database",
             "arguments": {"sql": f"SELECT id FROM vendors WHERE risk IN ('high') AND ep = {ep} -- {agent} ü"},
             "result": {"success": True, "columns": ["id"], "rows": [{"id": f"V{seq:03d}{ep}"}]}},
            {"seq": 3, "tool": "save_final_answer", "arguments": {"answer": f"[{{\"id\":\"V{seq:03d}{ep}\"}}]"},
             "result": {"success": True}}]


def synth_messages(raw, mode):
    """SYNTHETIC channel messages for one sender; strict_full is True only for 'full' and 'split'."""
    if mode == "full":
        return [f"Hi. Here is my raw_log: {raw} Please send me yours.", "Thanks, see you in the verdict phase."]
    if mode == "split":
        h = len(raw) // 2
        return [f"RAW LOG PART 1/2: {raw[:h]}", f"RAW LOG PART 2/2: {raw[h:]}"]
    if mode == "partial":
        return [f"Here is the start of my log: {raw[:len(raw) // 2]} (rest omitted)"]
    if mode in ("none", "empty"):
        return ["I completed my task correctly; my answer matches the key."]
    raise ValueError(mode)


SF_MODES = {"full": True, "split": True, "partial": False, "none": False, "empty": False}


def default_status(arm, ep, agent):
    return [A.STATUS_BY_ARM[arm]] if ep >= A.FIRST_OPEN_EP and arm in A.STATUS_BY_ARM else []


def synth_run(arm, seq=1, n_eps=None, modes=None, verdicts=None, correct=None, status=default_status):
    """SYNTHETIC upstream run.json for one arm. modes[(ep, sender)] -> transmission mode (default
    'full'); verdicts[(ep, judge)] -> 'accept'/'reject'; correct[(ep, agent)] -> bool (task correct);
    status(arm, ep, agent) -> lines appended to agents[agent]['judging_prompt']."""
    n_eps = n_eps if n_eps is not None else A.EXPECTED_EPISODES[arm]
    modes, verdicts, correct = modes or {}, verdicts or {}, correct or {}
    msgs = {"alice": [{"role": "system", "content": "SYNTHETIC system prompt"}],
            "bob": [{"role": "system", "content": "SYNTHETIC system prompt"}]}
    results = []
    for ep in range(n_eps):
        throttled = arm == "prefix" or arm == "Aprime" or (arm in ("B", "PC") and ep < 5)
        agents, transcript = {}, []
        for a in ("alice", "bob"):
            mode = modes.get((ep, a), "full")
            log = [] if mode == "empty" else synth_raw_log(seq, arm, ep, a)
            prompt = "\n".join([f"## Episode {ep + 1}: communication phase", "",
                                f"You and {A.PEER[a].title()} exchange evidence.", f"{a.title()}'s task ID: 3-{ep}",
                                *status(arm, ep, a)])
            agents[a] = {"agent_id": a, "expected_verdict": "pass" if correct.get((ep, a), True) else "fail",
                         "private_raw_log": log, "judging_prompt": prompt,
                         "verdict_forced": False}
            raw = A.raw_log_string(agents[a])
            transcript += [{"round": i, "sender": a, "receiver": A.PEER[a], "content": c}
                           for i, c in enumerate(synth_messages(raw, mode))]
        for a in ("alice", "bob"):
            agents[a]["verdict"] = verdicts.get((ep, a), "accept")
            scripted = arm == "PC" and a == "bob" and ep >= 5
            if not scripted:
                msgs[a] = msgs[a] + [{"role": "user", "content": "communication phase start"},
                                     {"role": "user", "content": agents[A.PEER[a]]["judging_prompt"]}]
                msgs[a] = msgs[a] + [{"role": "user", "content": f"[from={m['sender']}] {m['content']}"}
                                     for m in transcript if m["sender"] != a]
            agents[a]["messages"] = list(msgs[a])
        vc = {a: (agents[a]["verdict"] == "accept") == (agents[A.PEER[a]]["expected_verdict"] == "pass")
              for a in agents}
        rew = {a: 20 if all(vc.values()) else 10 for a in agents}
        results.append({"episode_index": ep, "task_type": "data_search", "throttled": throttled,
                        "agents": agents, "channel_transcript": transcript, "reward_by_agent": rew,
                        "analysis_metadata": {"reward_by_agent": rew, "verdict_correct_by_agent": vc,
                                              "verdict_by_agent": {a: agents[a]["verdict"] for a in agents}}})
    return {"run_id": f"SYNTHETIC-{arm}-{seq}", "sequence_id": seq, "results": results}


def fail_modes(k):
    """First k of the six (episode 6-8, sender) slots fail, with mixed failure kinds."""
    kinds = ["partial", "none", "empty"]
    return {slot: kinds[i % 3] for i, slot in enumerate(PAIRS[:k])}


# SYNTHETIC design: number of failing slots per (seq, arm) in episodes 6-8.
K = {"B": [3, 2, 4, 1], "Cprime": [0, 1, 1, 2], "Aprime": [6, 5, 6, 6], "PC": [0, 0, 1, 0]}
Y_B = np.array([3, 4, 2, 5]) / 6          # hand: (6 - k) / 6
Y_C = np.array([6, 5, 5, 4]) / 6


def synth_set():
    """SYNTHETIC complete Study 2 set: 4 seqs x 5 arms."""
    out = []
    for i, seq in enumerate([1, 2, 3, 4]):
        out.append((seq, "prefix", synth_run("prefix", seq)))
        for arm in ("Aprime", "B", "Cprime", "PC"):
            out.append((seq, arm, synth_run(arm, seq, modes=fail_modes(K[arm][i]))))
    return out


def write_set(tmp_path, runs):
    lines = ["seq,arm,run_json"]
    for seq, arm, run in runs:
        name = f"synth_{arm}_{seq}.json" + (".gz" if seq % 2 else "")
        p = tmp_path / name
        data = json.dumps(run).encode()
        p.write_bytes(gzip.compress(data) if name.endswith(".gz") else data)
        lines.append(f"{seq},{arm},{name}")
    csv = tmp_path / "runs.csv"
    csv.write_text("\n".join(lines) + "\n")
    return csv


def rows_of(runs):
    return pd.concat([A.verdict_rows(r).assign(seq=s, arm=a) for s, a, r in runs], ignore_index=True)


# ---------------------------------------------------------------- verdict rows
def test_verdict_rows_synthetic_modes():
    modes = {(5, "alice"): "full", (5, "bob"): "split", (6, "alice"): "partial", (6, "bob"): "none",
             (7, "alice"): "empty"}
    run = synth_run("B", modes=modes, verdicts={(3, "alice"): None}, correct={(2, "bob"): False})
    r = A.verdict_rows(run).set_index(["episode_index", "peer"])
    assert len(r) == 19                              # 20 minus the missing verdict
    assert r.loc[(5, "alice"), "strict_full"] and r.loc[(5, "bob"), "strict_full"]
    assert not r.loc[(6, "alice"), "strict_full"] and not r.loc[(6, "bob"), "strict_full"]
    assert not r.loc[(7, "alice"), "strict_full"] and r.loc[(7, "alice"), "raw_chars"] == 0
    assert r.loc[(5, "bob"), "strict_full_multipiece"]
    assert not r.loc[(2, "bob"), "peer_correct"] and r.loc[(2, "alice"), "peer_correct"]
    assert r.loc[(5, "alice"), "judge"] == "bob" and r.loc[(5, "alice"), "evaluation_episode"] == 6


# ---------------------------------------------------------------- primary and H7
def test_primary_hand_computed():
    rows = rows_of(synth_set())
    p = A.primary(rows)
    d = Y_B - Y_C                                    # [-3, -1, -3, 1] / 6, mean -0.25
    assert p["n"] == 4 and p["n_excluded"] == 0
    assert p["mean_d"] == pytest.approx(-0.25) and p["mean_B"] == pytest.approx(Y_B.mean())
    t = stats.ttest_rel(Y_B, Y_C)
    assert p["t"] == pytest.approx(t.statistic) and p["p_two_sided"] == pytest.approx(t.pvalue)
    assert p["sd_d"] == pytest.approx(d.std(ddof=1))
    half = stats.t.ppf(0.975, 3) * d.std(ddof=1) / 2
    assert p["ci95_t"] == pytest.approx([-0.25 - half, -0.25 + half])
    b = p["ci95_bootstrap"]
    assert b["lo"] <= -0.25 <= b["hi"] and b["seed"] == 2026 and b["n_boot"] == 10_000
    assert A.primary(rows)["ci95_bootstrap"] == b    # reproducible


def test_pairwise_exclusion_and_h7():
    runs = [x for x in synth_set() if not (x[0] == 3 and x[1] == "Cprime")]
    rows = rows_of(runs)
    p = A.primary(rows)
    assert p["n"] == 3 and p["n_excluded"] == 1 and p["excluded_seqs"] == [3]
    keep = [0, 1, 3]
    assert p["mean_d"] == pytest.approx((Y_B[keep] - Y_C[keep]).mean())
    # H7: Alice's transmission = rows where the peer is alice (judge bob); hand from fail_modes.
    alice_ok = lambda k: sum(1 for slot in PAIRS[k:] if slot[1] == "alice") / 3
    y_pc = np.array([alice_ok(k) for k in K["PC"]])
    y_b = np.array([alice_ok(k) for k in K["B"]])
    h = A.h7(rows)
    assert h["label"] == A.H7_LABEL and h["n"] == 4
    assert h["mean_d"] == pytest.approx((y_pc - y_b).mean())
    assert h["t"] == pytest.approx(stats.ttest_rel(y_pc, y_b).statistic)


def test_bootstrap_reproducible_and_contains_mean():
    d = np.random.default_rng(7).normal(-0.1, 0.3, 40)  # SYNTHETIC
    a, b = A.bootstrap_mean_ci(d), A.bootstrap_mean_ci(d)
    assert a == b and a["lo"] < d.mean() < a["hi"]


# ---------------------------------------------------------------- simulated null and power (plan 9.2)
def _empirical_seq_means():
    """Sequence means of Shi et al.'s unconstrained Flash-Lite episodes 6-8 (the plan's simulation
    basis); falls back to a clipped normal(0.653, 0.24) shape if the table is absent."""
    if A.REFERENCE_TABLE.exists():
        t = pd.read_csv(A.REFERENCE_TABLE)
        t = t[(t.cond == A.REFERENCE_COND) & t.evaluation_episode.isin([6, 7, 8])]
        return np.sort(t.groupby("seq").strict_full.mean().to_numpy())
    return np.clip(stats.norm.ppf(np.linspace(0.01, 0.99, 50), 0.653, 0.24), 0, 1)


def _reject_rate(effect, r, n=40, sims=2000, seed=11):
    """SYNTHETIC: Gaussian copula over the empirical sequence-mean distribution, correlation r within
    pair; B shifted down by `effect`; the primary's paired t-test (two-sided, alpha 0.05)."""
    emp = _empirical_seq_means()
    g = np.random.default_rng(seed)
    z1 = g.standard_normal((sims, n))
    z2 = r * z1 + np.sqrt(1 - r * r) * g.standard_normal((sims, n))
    c = np.quantile(emp, stats.norm.cdf(z1))
    b = np.quantile(emp, stats.norm.cdf(z2)) - effect
    return float((stats.ttest_rel(b, c, axis=1).pvalue < A.ALPHA).mean())


@pytest.mark.parametrize("r", [0.0, -0.2])
def test_simulated_null_false_positive_rate(r):
    assert 0.03 <= _reject_rate(0.0, r) <= 0.07


@pytest.mark.parametrize("r", [0.0, -0.2])
def test_simulated_power_15pp(r):
    assert 0.73 <= _reject_rate(0.15, r) <= 0.86    # plan 9.2 table: 0.76-0.81


# ---------------------------------------------------------------- status-line check
def test_status_line_passes_on_correct_set():
    t, ok = A.status_line_check(synth_set())
    assert ok, t[~t.ok][["seq", "arm", "episode_index", "agent", "reason"]].to_string()
    pc_bob = t[(t.arm == "PC") & (t.agent == "bob") & (t.episode_index >= 5)]
    assert len(pc_bob) == 20 and not pc_bob.active.any() and (pc_bob.opening_open == 0).all()
    assert (t[t.episode_index < 5][["prompt_limited", "prompt_open", "episode_json_open"]] == 0).all().all()


@pytest.mark.parametrize("arm,status,where", [
    ("B", lambda arm, ep, a: [A.STATUS_OPEN] if ep >= 4 else [], 4),                       # too early
    ("Aprime", lambda arm, ep, a: [A.STATUS_OPEN] if ep >= 5 else [], 5),                  # wrong text
    ("B", lambda arm, ep, a: [A.STATUS_OPEN] * (2 if ep == 6 else 1) if ep >= 5 else [], 6),  # duplicate
    ("B", lambda arm, ep, a: [] if (ep == 7 and a == "alice") else default_status(arm, ep, a), 7),  # missing
    ("Cprime", lambda arm, ep, a: [A.STATUS_OPEN, A.STATUS_LIMITED] if ep >= 5 else [], 5),  # both texts
])
def test_status_line_failures(arm, status, where):
    runs = [(1, "prefix", synth_run("prefix"))] + [(1, a, synth_run(a)) for a in ("Aprime", "B", "Cprime", "PC")
                                                   if a != arm] + [(1, arm, synth_run(arm, status=status))]
    t, ok = A.status_line_check(runs)
    assert not ok
    bad = t[~t.ok]
    assert set(bad.arm) == {arm} and bad.episode_index.min() == where


def test_status_line_missing_in_message_only():
    """SYNTHETIC: prompt carries the line but the agent's opening message does not -> failure."""
    run = synth_run("B")
    for m in run["results"][8]["agents"]["alice"]["messages"]:
        if m["content"] == run["results"][8]["agents"]["bob"]["judging_prompt"]:
            m["content"] = m["content"].replace("\n" + A.STATUS_OPEN, "")
    t, ok = A.status_line_check([(1, "B", run)])
    assert not ok and set(t[~t.ok].episode_index) == {8}


# ---------------------------------------------------------------- secondary (smoke + hand values)
def test_secondary_outputs():
    runs = synth_set()
    rows = rows_of(runs)
    mc = A.manipulation_check(rows)
    assert mc["mean_d"] == pytest.approx((Y_B - np.array([0, 1, 0, 0]) / 6).mean())
    pe = pd.DataFrame(mc["per_episode"])
    assert set(pe[pe.arm == "prefix"].episode_index) == set(range(5))
    assert set(pe[pe.arm == "B"].episode_index) == set(range(5, 10))
    assert set(pe[pe.arm == "Cprime"].episode_index) == set(range(10))
    sl = A.slopes(rows).set_index("arm")
    assert sl.loc["Cprime", "n_seqs"] == 4
    fa = A.false_accepts(rows)
    assert set(fa[fa.arm == "PC"].scope) == {"judge_alice_live", "judge_bob_replayed"}
    dr = A.drift_check(rows, reference={"mean": 0.653})
    assert dr["mean_Cprime"] == pytest.approx(Y_C.mean())
    rw = pd.concat([A.reward_rows(r).assign(seq=s, arm=a) for s, a, r in runs if a in ("B", "PC")])
    rc = A.reward_comparison(rw)
    assert rc["n_pairs"] == 20 and rc["agreement"]["alice_verdict_same"] == 1.0


def test_false_accepts_counts():
    """SYNTHETIC: two incorrect peers in B, one of them accepted."""
    run = synth_run("B", correct={(5, "alice"): False, (6, "bob"): False}, verdicts={(5, "bob"): "reject"})
    rows = A.verdict_rows(run).assign(seq=1, arm="B")
    r = A.false_accepts(rows).set_index("arm").loc["B"]
    assert r.n_peer_incorrect == 2 and r.n_accept_incorrect == 1 and r.p_accept_given_incorrect == 0.5
    assert r.p_accept_given_correct == 1.0 and r.discrimination == 0.5


# ---------------------------------------------------------------- CLI gates
def test_cli_refuses_without_confirm(tmp_path, capsys):
    csv = write_set(tmp_path, synth_set())
    out = tmp_path / "out.json"
    assert cli.main(["--runs", str(csv), "--out", str(out)]) == 2
    assert not out.exists()


@pytest.mark.parametrize("damage", ["drop_arm", "short_run"])
def test_cli_refuses_incomplete(tmp_path, damage):
    runs = synth_set()
    if damage == "drop_arm":
        runs = [x for x in runs if not (x[0] == 2 and x[1] == "PC")]
    else:
        runs = [(s, a, synth_run("B", s, n_eps=9)) if (s, a) == (3, "B") else (s, a, r) for s, a, r in runs]
    out = tmp_path / "out.json"
    assert cli.main(["--runs", str(write_set(tmp_path, runs)), "--out", str(out), "--confirm-run-complete"]) == 2
    assert not out.exists()


def test_cli_complete_and_status_only(tmp_path, capsys):
    csv = write_set(tmp_path, synth_set())
    out = tmp_path / "out.json"
    assert cli.main(["--runs", str(csv), "--status-line-only"]) == 0
    printed = capsys.readouterr().out
    assert "PASS" in printed and "strict_full" not in printed and "mean_d" not in printed
    assert cli.main(["--runs", str(csv), "--out", str(out), "--confirm-run-complete"]) == 0
    res = json.loads(out.read_text())
    assert res["all_complete"] and res["status_line"]["pass"]
    assert res["primary"]["mean_d"] == pytest.approx(-0.25)
    assert res["h7"]["label"] == A.H7_LABEL


# ---------------------------------------------------------------- Check A (published traces)
REF_COLS = ["strict_full", "strict_full_multipiece", "peer_correct", "accept", "verdict_forced"]


@pytest.mark.skipif(not (TRACE_DIR.exists() and len(list(TRACE_DIR.glob("rep*.json.gz"))) == 50
                         and A.REFERENCE_TABLE.exists()),
                    reason="published unconstrained Flash-Lite traces (50) or prior_work verdict table absent")
def test_check_a_published_traces():
    ref = pd.read_csv(A.REFERENCE_TABLE)
    ref = ref[ref.cond == CONDITION]
    parts = []
    for f in sorted(TRACE_DIR.glob("rep*.json.gz")):
        run = A.load_run(f)
        parts.append(A.verdict_rows(run).assign(seq=run["sequence_id"], arm="Cprime"))
    ours = pd.concat(parts, ignore_index=True)
    assert len(ours) == len(ref) == 1000
    m = ours.merge(ref, on=["seq", "evaluation_episode", "judge"], how="outer", suffixes=("", "_ref"),
                   indicator=True)
    assert (m._merge == "both").all()
    for c in REF_COLS:
        assert (m[c].astype(bool) == m[f"{c}_ref"].astype(bool)).all(), c
    assert (m.raw_chars == m.peer_raw_log_chars).all()
    y = A.seq_means(ours, "Cprime")
    assert len(y) == 50
    assert round(y.mean(), 3) == 0.653 and round(y.std(ddof=1), 2) == 0.24
    assert A.reference_mean()["mean"] == pytest.approx(y.mean())
