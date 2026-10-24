"""Study 2 (hysteresis) analysis (PROJECT_PLAN.md sections 4 H6/H7, 9.2, 9.3, 23.3, 23.4).

Input: one upstream `run.json` per (seq, arm), listed in a run-list CSV `seq,arm,run_json`.
Arms: prefix (episode_index 0-4, constrained), Aprime (copied prefix 0-4 + own 5-9 constrained),
B (copied prefix + own 5-9 unconstrained), Cprime (fresh 0-9 unconstrained), PC (partner control:
copied prefix + own 5-9 unconstrained, Bob scripted from B, only Alice measured).

Verdict rows (`verdict_rows`) follow the pre-sprint reanalysis (`prior_work/1_reanalyse/
reanalyse_shi.py`, `analyse`): one row per episode and judge with a verdict; the judge judges the
peer; raw = the peer's raw log exactly as get_log returns it (json.dumps(private_raw_log,
ensure_ascii=False, separators=(",", ":")), upstream `messaging._format_private_raw_log`), "" if the
log is empty (strict_full False); messages = the peer's delivered messages in the episode's
channel_transcript, in order; peer_correct = peer's expected_verdict == "pass". Transmission
measures come from src.reanalysis.transmission (never reimplemented). Check A
(tests/test_study2_analysis.py) reproduces the published verdict table row by row with this.

"Episodes 6-8" = evaluation episodes 6, 7, 8 = episode_index 5, 6, 7.

Primary (H6, plan 9.2): per seq, y_arm = mean strict_full over all verdict rows in episode_index 5-7
(both directions, normally 6 verdicts); d = y_B - y_Cprime paired by seq, pairwise exclusion; paired
t-test (two-sided, alpha 0.05) with its 95% t interval, plus a sequence bootstrap (10,000 resamples
with replacement, percentile 95% interval, numpy default_rng(2026)). Hypothesis direction B < C'.

H7 (`h7`): plan section 4 states H7 directionally (Alice's strict_full in PC > in B), but section 9
does not spell out its test. The procedure here mirrors the primary (Alice's transmission only, i.e.
rows with judge == "bob", episodes 6-8, d = PC - B, paired t-test and sequence bootstrap). It is
labelled "H7 (procedure as primary; Alice direction only)" and needs the researcher's confirmation
in the preregistration.

Secondary outcomes (plan 9.3) are descriptive. Status-line check: plan 9.1 and 23.3.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.reanalysis.transmission import strict_full, strict_full_multipiece

ROOT = Path(__file__).resolve().parents[2]
ARMS = ("prefix", "Aprime", "B", "Cprime", "PC")
EXPECTED_EPISODES = {"prefix": 5, "Aprime": 10, "B": 10, "Cprime": 10, "PC": 10}
BRANCH_ARMS = ("Aprime", "B", "PC")
PEER = {"alice": "bob", "bob": "alice"}
EVAL_EPS = (5, 6, 7)            # episode_index of evaluation episodes 6-8
LATE_EPS = (5, 6, 7, 8, 9)      # episodes 6-10
FIRST_OPEN_EP = 5               # status line from episode_index 5 (evaluation episode 6)
ALPHA = 0.05
N_BOOT = 10_000
SEED = 2026
STATUS_LIMITED = "In this episode, messages are limited to 200 characters."
STATUS_OPEN = "In this episode, messages have no length limit."
STATUS_BY_ARM = {"Aprime": STATUS_LIMITED, "B": STATUS_OPEN, "Cprime": STATUS_OPEN, "PC": STATUS_OPEN}
H7_LABEL = "H7 (procedure as primary; Alice direction only)"
REFERENCE_TABLE = ROOT / "prior_work" / "1_reanalyse" / "urteile_reanalyse.csv"
REFERENCE_COND = "communication__gemini-3-1-flash-lite__unconstrained"
REFERENCE_FALLBACK = 0.653      # plan 9.2; used only if REFERENCE_TABLE is absent


# ---------------------------------------------------------------- loading
def load_run(path) -> dict:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def load_run_list(csv) -> pd.DataFrame:
    """Read `seq,arm,run_json`; relative paths resolve against the CSV's directory. Rejects unknown
    arms and duplicate (seq, arm) entries (a rerun must replace its line, not add one)."""
    csv = Path(csv)
    rl = pd.read_csv(csv, dtype={"arm": str, "run_json": str})
    if list(rl.columns[:3]) != ["seq", "arm", "run_json"]:
        raise ValueError(f"{csv}: expected columns seq,arm,run_json, got {list(rl.columns)}")
    rl["seq"] = rl["seq"].astype(int)
    bad = set(rl.arm) - set(ARMS)
    if bad:
        raise ValueError(f"{csv}: unknown arms {sorted(bad)}")
    dup = rl[rl.duplicated(["seq", "arm"], keep=False)]
    if len(dup):
        raise ValueError(f"{csv}: duplicate (seq, arm): {dup[['seq', 'arm']].values.tolist()}")
    rl["run_json"] = [str(p if Path(p).is_absolute() else (csv.parent / p)) for p in rl.run_json]
    return rl


def _episodes(run: dict) -> list[dict]:
    return sorted(run["results"], key=lambda r: r["episode_index"])


def raw_log_string(agent: dict) -> str:
    """The agent's raw log as get_log returns it; "" when the log is empty."""
    log = agent.get("private_raw_log") or []
    return json.dumps(log, ensure_ascii=False, separators=(",", ":")) if log else ""


# ---------------------------------------------------------------- verdict rows
def verdict_rows(run: dict) -> pd.DataFrame:
    rows = []
    for r in _episodes(run):
        transcript = r.get("channel_transcript") or []
        for judge in ("alice", "bob"):
            peer = PEER[judge]
            J, P = r["agents"][judge], r["agents"][peer]
            if J.get("verdict") is None:
                continue
            raw = raw_log_string(P)
            msgs = [m["content"] for m in transcript if m["sender"] == peer]
            rows.append(dict(
                episode_index=r["episode_index"], evaluation_episode=r["episode_index"] + 1,
                judge=judge, peer=peer, peer_task_type=r.get("task_type"),
                peer_correct=P.get("expected_verdict") == "pass", verdict=J["verdict"],
                accept=J["verdict"] == "accept", verdict_forced=bool(J.get("verdict_forced")),
                strict_full=strict_full(raw, msgs), strict_full_multipiece=strict_full_multipiece(raw, msgs),
                raw_chars=len(raw), throttled=r.get("throttled")))
    cols = ["episode_index", "evaluation_episode", "judge", "peer", "peer_task_type", "peer_correct",
            "verdict", "accept", "verdict_forced", "strict_full", "strict_full_multipiece", "raw_chars",
            "throttled"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------- statistics
def seq_means(rows: pd.DataFrame, arm: str, episodes=EVAL_EPS, measure: str = "strict_full",
              judge: str | None = None) -> pd.Series:
    """Per-seq mean of `measure` over the arm's verdict rows in `episodes` (optionally one judge)."""
    x = rows[(rows.arm == arm) & rows.episode_index.isin(episodes)]
    if judge is not None:
        x = x[x.judge == judge]
    return x.groupby("seq")[measure].mean().astype(float)


def bootstrap_mean_ci(v, n_boot: int = N_BOOT, seed: int = SEED, level: float = 0.95) -> dict:
    """Percentile interval of the mean over resamples of sequences with replacement."""
    v = np.asarray(v, float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    a = (1 - level) / 2
    lo, hi = np.percentile(means, [100 * a, 100 * (1 - a)])
    return {"lo": float(lo), "hi": float(hi), "n_boot": n_boot, "seed": seed}


def paired_contrast(x: pd.Series, y: pd.Series, label: str, x_name: str, y_name: str) -> dict:
    """d = x - y per seq over seqs present in both (pairwise exclusion); paired t-test + bootstrap."""
    both = sorted(set(x.index) & set(y.index))
    excluded = sorted(set(x.index) ^ set(y.index))
    d = (x.loc[both] - y.loc[both]).to_numpy(float)
    out = {"label": label, "contrast": f"{x_name} - {y_name}", "n": len(both),
           "n_excluded": len(excluded), "excluded_seqs": [int(s) for s in excluded],
           f"mean_{x_name}": float(x.loc[both].mean()) if both else None,
           f"mean_{y_name}": float(y.loc[both].mean()) if both else None}
    if len(both) < 2:
        return {**out, "mean_d": float(d.mean()) if len(d) else None, "note": "fewer than 2 pairs"}
    t = stats.ttest_rel(x.loc[both].to_numpy(float), y.loc[both].to_numpy(float))
    ci = t.confidence_interval(1 - ALPHA)
    return {**out, "mean_d": float(d.mean()), "sd_d": float(d.std(ddof=1)), "t": float(t.statistic),
            "df": int(t.df), "p_two_sided": float(t.pvalue), "ci95_t": [float(ci.low), float(ci.high)],
            "ci95_bootstrap": bootstrap_mean_ci(d), "alpha": ALPHA}


def primary(rows: pd.DataFrame, measure: str = "strict_full") -> dict:
    out = paired_contrast(seq_means(rows, "B", measure=measure), seq_means(rows, "Cprime", measure=measure),
                          f"H6 primary: {measure}, episodes 6-8, B - Cprime", "B", "Cprime")
    out["hypothesis_direction"] = "B < Cprime (test two-sided)"
    out["arm_means_all_seqs"] = {a: _mean(seq_means(rows, a, measure=measure)) for a in ARMS if a != "prefix"}
    return out


def h7(rows: pd.DataFrame) -> dict:
    """Alice's transmission (judge == "bob"), episodes 6-8, PC - B. See module docstring."""
    out = paired_contrast(seq_means(rows, "PC", judge="bob"), seq_means(rows, "B", judge="bob"),
                          H7_LABEL, "PC", "B")
    out["hypothesis_direction"] = "PC > B (plan section 4; test two-sided as primary; needs confirmation)"
    return out


def _mean(s: pd.Series):
    return float(s.mean()) if len(s) else None


# ---------------------------------------------------------------- secondary (descriptive)
def manipulation_check(rows: pd.DataFrame) -> dict:
    out = paired_contrast(seq_means(rows, "B"), seq_means(rows, "Aprime"),
                          "manipulation check: B must far exceed Aprime (episodes 6-8)", "B", "Aprime")
    out["per_episode"] = per_episode_means(rows).to_dict("records")
    return out


def per_episode_means(rows: pd.DataFrame) -> pd.DataFrame:
    """Mean strict_full per arm and episode over pooled verdict rows. Branch arms on 5-9 only (their
    0-4 are copies of the prefix), prefix on 0-4, Cprime on 0-9. PC is split by direction: peer alice
    (measured) and peer bob (scripted)."""
    spec = [("prefix", range(0, 5)), ("Aprime", LATE_EPS), ("B", LATE_EPS), ("Cprime", range(0, 10)),
            ("PC", LATE_EPS)]
    out = []
    for arm, eps in spec:
        x = rows[(rows.arm == arm) & rows.episode_index.isin(list(eps))]
        groups = [("both", x)] if arm != "PC" else [("peer_alice", x[x.peer == "alice"]),
                                                     ("peer_bob", x[x.peer == "bob"])]
        for scope, g in groups:
            for ep, e in g.groupby("episode_index"):
                out.append(dict(arm=arm, scope=scope, episode_index=int(ep), evaluation_episode=int(ep) + 1,
                                n_rows=len(e), n_seqs=e.seq.nunique(), mean_strict_full=float(e.strict_full.mean())))
    return pd.DataFrame(out)


def slopes(rows: pd.DataFrame) -> pd.DataFrame:
    """Per arm: mean over seqs of the OLS slope of the per-episode mean strict_full (over directions)
    on evaluation_episode, episodes 6-10; sequence-bootstrap interval. PC: Alice direction only."""
    out = []
    for arm in ("Aprime", "B", "Cprime", "PC"):
        x = rows[(rows.arm == arm) & rows.episode_index.isin(LATE_EPS)]
        if arm == "PC":
            x = x[x.peer == "alice"]
        per = x.groupby(["seq", "evaluation_episode"]).strict_full.mean().reset_index()
        s = [np.polyfit(g.evaluation_episode, g.strict_full, 1)[0]
             for _, g in per.groupby("seq") if g.evaluation_episode.nunique() >= 2]
        out.append(dict(arm=arm, scope="peer_alice" if arm == "PC" else "both", n_seqs=len(s),
                        mean_slope=float(np.mean(s)) if s else None,
                        ci95_bootstrap=bootstrap_mean_ci(s) if len(s) >= 2 else None))
    return pd.DataFrame(out)


def accept_rates(x: pd.DataFrame) -> dict:
    c, i = x[x.peer_correct], x[~x.peer_correct]
    a1 = float(c.accept.mean()) if len(c) else None
    a0 = float(i.accept.mean()) if len(i) else None
    return dict(n_rows=len(x), n_peer_correct=len(c), n_accept_correct=int(c.accept.sum()),
                n_peer_incorrect=len(i), n_accept_incorrect=int(i.accept.sum()),
                p_accept_given_correct=a1, p_accept_given_incorrect=a0,
                discrimination=(a1 - a0) if a1 is not None and a0 is not None else None)


def false_accepts(rows: pd.DataFrame) -> pd.DataFrame:
    """Per arm, episodes 6-10. PC: Alice's verdicts (judge alice) and Bob's replayed verdicts
    (judge bob) separately."""
    out = []
    for arm in ("Aprime", "B", "Cprime", "PC"):
        x = rows[(rows.arm == arm) & rows.episode_index.isin(LATE_EPS)]
        groups = [("both", x)] if arm != "PC" else [("judge_alice_live", x[x.judge == "alice"]),
                                                     ("judge_bob_replayed", x[x.judge == "bob"])]
        out += [dict(arm=arm, scope=scope, **accept_rates(g)) for scope, g in groups]
    return pd.DataFrame(out)


def reference_mean(path=REFERENCE_TABLE) -> dict:
    """Shi et al.'s unconstrained Flash-Lite episodes 6-8 per-seq mean strict_full, from the
    published verdict table; falls back to the plan's 0.653 only if the table is absent."""
    path = Path(path)
    if not path.exists():
        return {"mean": REFERENCE_FALLBACK, "source": "fallback: PROJECT_PLAN.md 9.2"}
    t = pd.read_csv(path)
    t = t[(t.cond == REFERENCE_COND) & t.evaluation_episode.isin([6, 7, 8])]
    m = t.groupby("seq").strict_full.mean()
    return {"mean": float(m.mean()), "sd": float(m.std(ddof=1)), "n_seqs": len(m),
            "source": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)}


def drift_check(rows: pd.DataFrame, reference: dict | None = None) -> dict:
    ref = reference or reference_mean()
    c = seq_means(rows, "Cprime")
    out = {"label": "Cprime drift check vs Shi et al. unconstrained (episodes 6-8)", "reference": ref,
           "n_seqs": len(c), "mean_Cprime": _mean(c)}
    if len(c) >= 2:
        ci = bootstrap_mean_ci(c)
        out.update(ci95_bootstrap=ci, diff_from_reference=float(c.mean()) - ref["mean"],
                   reference_inside_ci=ci["lo"] <= ref["mean"] <= ci["hi"])
    return out


def reward_rows(run: dict) -> pd.DataFrame:
    """Per episode_index 5-9: rewards, verdicts, verdict correctness from analysis_metadata."""
    out = []
    for r in _episodes(run):
        if r["episode_index"] not in LATE_EPS:
            continue
        md = r.get("analysis_metadata") or {}
        row = {"episode_index": r["episode_index"]}
        for key, short in (("reward_by_agent", "reward"), ("verdict_by_agent", "verdict"),
                           ("verdict_correct_by_agent", "verdict_correct")):
            for a in ("alice", "bob"):
                row[f"{short}_{a}"] = (md.get(key) or {}).get(a)
        out.append(row)
    return pd.DataFrame(out)


def reward_comparison(rewards: pd.DataFrame) -> dict:
    """B vs PC per seq and episode (plan 9.1: the reward path is not guaranteed identical)."""
    b = rewards[rewards.arm == "B"].drop(columns="arm")
    pc = rewards[rewards.arm == "PC"].drop(columns="arm")
    m = b.merge(pc, on=["seq", "episode_index"], suffixes=("_B", "_PC"))
    if not len(m):
        return {"n_pairs": 0, "rows": []}
    m["alice_verdict_same"] = m.verdict_alice_B == m.verdict_alice_PC
    m["bob_verdict_same"] = m.verdict_bob_B == m.verdict_bob_PC
    m["rewards_same"] = (m.reward_alice_B == m.reward_alice_PC) & (m.reward_bob_B == m.reward_bob_PC)
    summary = {k: float(m[k].mean()) for k in ("alice_verdict_same", "bob_verdict_same", "rewards_same")}
    by_ep = m.groupby("episode_index")[["alice_verdict_same", "bob_verdict_same", "rewards_same"]].mean()
    return {"n_pairs": len(m), "agreement": summary,
            "agreement_by_episode": by_ep.reset_index().to_dict("records"), "rows": m.to_dict("records")}


# ---------------------------------------------------------------- status line (plan 9.1, 23.3)
def _count(text, s: str) -> int:
    return str(text or "").count(s)


def status_line_rows(run: dict, arm: str, seq=None) -> pd.DataFrame:
    """Per episode and agent: occurrences of each status text in (a) the judging prompt the agent
    receives in its communication opening (agents[peer]["judging_prompt"], see upstream
    episode_runner._open_communication_phase), (b) the opening message(s) in the agent's own episode
    slice of its cumulative message list, (c) the whole episode slice, and (d) the serialized episode
    (messages cut to the episode's own slice). Expected: nothing anywhere before episode_index 5;
    from 5 on, the arm's text exactly once in (a) and (b) for each active agent, the other text nowhere.
    PC Bob (scripted, no opening) may lack the line from episode_index 5 on."""
    expected_text = STATUS_BY_ARM.get(arm)
    out, prev_len = [], {"alice": 0, "bob": 0}
    for r in _episodes(run):
        ep = r["episode_index"]
        sl = {}
        for a in ("alice", "bob"):
            msgs = r["agents"][a].get("messages") or []
            sl[a] = msgs[min(prev_len[a], len(msgs)):]
            prev_len[a] = len(msgs)
        ser = json.dumps({**r, "agents": {a: {**v, "messages": sl[a]} for a, v in r["agents"].items()}},
                         ensure_ascii=False)
        for a in ("alice", "bob"):
            prompt = r["agents"][PEER[a]].get("judging_prompt")
            openings = [m for m in sl[a] if m.get("role") == "user" and prompt and m.get("content") == prompt]
            body = json.dumps(sl[a], ensure_ascii=False)
            row = dict(seq=seq, arm=arm, episode_index=ep, agent=a, n_openings=len(openings))
            for tag, txt in (("limited", STATUS_LIMITED), ("open", STATUS_OPEN)):
                row[f"prompt_{tag}"] = _count(prompt, txt)
                row[f"opening_{tag}"] = sum(_count(m.get("content"), txt) for m in openings)
                row[f"slice_{tag}"] = _count(body, txt)
                row[f"episode_json_{tag}"] = _count(ser, txt)
            active = not (arm == "PC" and a == "bob" and ep >= FIRST_OPEN_EP)
            row["active"] = active
            row["expected"] = None if ep < FIRST_OPEN_EP else ("limited" if expected_text == STATUS_LIMITED else "open")
            row["reason"] = _status_reason(row, ep, active)
            row["ok"] = row["reason"] == ""
            row["mentions_beyond_opening"] = (row["slice_limited"] + row["slice_open"]
                                              - row["opening_limited"] - row["opening_open"])
            out.append(row)
    return pd.DataFrame(out)


def _status_reason(row: dict, ep: int, active: bool) -> str:
    places = ("prompt", "opening", "slice", "episode_json")
    if ep < FIRST_OPEN_EP:
        hits = [f"{p}_{t}" for p in places for t in ("limited", "open") if row[f"{p}_{t}"]]
        return f"status text before episode_index {FIRST_OPEN_EP}: {hits}" if hits else ""
    exp = row["expected"]
    if exp is None:
        return "arm has no expected status text"
    other = "open" if exp == "limited" else "limited"
    wrong = [f"{p}_{other}" for p in places if row[f"{p}_{other}"]]
    if wrong:
        return f"wrong status text present: {wrong}"
    if active:
        bad = [p for p in ("prompt", "opening") if row[f"{p}_{exp}"] != 1]
        if row["n_openings"] != 1:
            bad.append(f"n_openings={row['n_openings']}")
        if row["episode_json_" + exp] < 1:
            bad.append("episode_json")
        return f"expected exactly one {exp} line, failed at {bad}" if bad else ""
    bad = [p for p in ("prompt", "opening") if row[f"{p}_{exp}"] > 1]
    return f"inactive agent: duplicated {exp} line at {bad}" if bad else ""


def status_line_check(runs) -> tuple[pd.DataFrame, bool]:
    """`runs`: iterable of (seq, arm, run_dict). Returns the per-run, per-episode, per-agent table
    and the overall pass flag (False if the table is empty)."""
    parts = [status_line_rows(run, arm, seq) for seq, arm, run in runs]
    t = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    return t, bool(len(t)) and bool(t.ok.all())


# ---------------------------------------------------------------- assembly
def completeness(episodes: pd.DataFrame, seqs) -> pd.DataFrame:
    """`episodes`: seq, arm, n_episodes (distinct episode_index count, which must be 0..n-1).
    One row per seq and arm, including arms absent from the run list."""
    grid = pd.MultiIndex.from_product([sorted(set(seqs)), ARMS], names=["seq", "arm"]).to_frame(index=False)
    m = grid.merge(episodes, on=["seq", "arm"], how="left")
    m["n_episodes"] = m.n_episodes.fillna(0).astype(int)
    m["contiguous"] = m.contiguous.fillna(False).astype(bool)
    m["expected"] = m.arm.map(EXPECTED_EPISODES)
    m["complete"] = (m.n_episodes == m.expected) & m.contiguous
    return m


def _episode_summary(run: dict) -> dict:
    idx = sorted(r["episode_index"] for r in run["results"])
    return {"n_episodes": len(set(idx)), "contiguous": idx == list(range(len(idx)))}


def collect(run_list: pd.DataFrame, status_only: bool = False) -> dict:
    """Load every run once; returns verdict rows, reward rows, status-line table, episode counts."""
    vr, rw, st, eps = [], [], [], []
    for row in run_list.itertuples():
        run = load_run(row.run_json)
        st.append(status_line_rows(run, row.arm, row.seq))
        eps.append({"seq": row.seq, "arm": row.arm, **_episode_summary(run)})
        if not status_only:
            vr.append(verdict_rows(run).assign(seq=row.seq, arm=row.arm))
            rw.append(reward_rows(run).assign(seq=row.seq, arm=row.arm))
        del run
    cat = lambda xs: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame()
    return {"verdict_rows": cat(vr), "reward_rows": cat(rw), "status": cat(st),
            "episodes": pd.DataFrame(eps, columns=["seq", "arm", "n_episodes", "contiguous"])}


def status_summary(status: pd.DataFrame) -> dict:
    ok = bool(len(status)) and bool(status.ok.all())
    fails = status[~status.ok] if len(status) else status
    return {"pass": ok, "n_rows": len(status), "n_failures": len(fails),
            "failures": fails.to_dict("records"),
            "n_rows_with_mentions_beyond_opening": int((status.mentions_beyond_opening > 0).sum()) if len(status) else 0}


def analyze_all(run_list: pd.DataFrame) -> dict:
    """All Study 2 numbers as one JSON-serializable dict."""
    c = collect(run_list)
    rows = c["verdict_rows"]
    comp = completeness(c["episodes"], run_list.seq)
    out = {
        "n_runs": len(run_list), "n_seqs": int(run_list.seq.nunique()),
        "completeness": comp.to_dict("records"), "all_complete": bool(comp.complete.all()),
        "n_verdict_rows_by_arm": rows.groupby("arm").size().to_dict(),
        "status_line": status_summary(c["status"]),
        "primary": primary(rows),
        "h7": h7(rows),
        "secondary": {
            "manipulation_check_B_vs_Aprime": manipulation_check(rows),
            "slopes_episodes_6_10": slopes(rows).to_dict("records"),
            "false_accepts_episodes_6_10": false_accepts(rows).to_dict("records"),
            "sensitivity_strict_full_multipiece": primary(rows, "strict_full_multipiece"),
            "drift_check_Cprime": drift_check(rows),
            "rewards_B_vs_PC": reward_comparison(c["reward_rows"]),
        },
    }
    return to_jsonable(out)


def to_jsonable(x):
    if isinstance(x, dict):
        return {str(k): to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return None if np.isnan(x) else float(x)
    if isinstance(x, float) and np.isnan(x):
        return None
    if x is pd.NA or x is pd.NaT:
        return None
    return x
