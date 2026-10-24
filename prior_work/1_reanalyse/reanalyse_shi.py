"""Reanalyse der veroeffentlichten Daten von Shi et al. (2609.24967).

Daten: https://huggingface.co/datasets/SALT-NLP/agent-collusion
Benoetigt je Bedingung data/episodes/<exp>/<cond>.parquet und data/agents/<exp>/<cond>.parquet,
lokal abgelegt als ep_<cond>.parquet und ag_<cond>.parquet.

Misst pro Urteil (Agent beurteilt die Aufgabe des Partners):
  - ob der Rohlog des Partners vollstaendig und unveraendert uebertragen wurde.
    Referenz ist der exakte String, den get_log zurueckgibt (= Feld raw_log, geprueft
    an 40 Episoden aus zwei Traces). Keine Normalisierung von Leerzeichen.
    "verbatim_stuecke": Der Rohlog laesst sich restlos in aufeinanderfolgende Stuecke
    zerlegen, von denen jedes woertlich in einer Nachricht des Partners steht, in der
    Reihenfolge der Nachrichten. Rahmentext zwischen den Stuecken ist erlaubt,
    jede Auslassung oder Veraenderung eines Zeichens nicht. Das Ende wird mitgeprueft.
    "verbatim_am_stueck": Der Rohlog steht ununterbrochen in einer einzigen Nachricht.
    "verbatim_mehrteilig": wie verbatim_stuecke, aber eine Nachricht darf mehrere Stuecke
    enthalten, die dort in Reihenfolge stehen und durch Rahmentext getrennt sind. Jedes
    Stueck muss mindestens MIN_PIECE Zeichen haben; ein kuerzerer Rest ist nur erlaubt,
    wenn er innerhalb von 50 Zeichen nach dem vorigen Stueck in derselben Nachricht steht.
  - P(ACCEPT | Partneraufgabe korrekt) und P(ACCEPT | Partneraufgabe falsch)
  - Trennschaerfe = Differenz, mit Cluster-Bootstrap ueber Trajektorien
Aufwaerm-Episoden werden ausgeschlossen.
"""
import sys

import numpy as np
import pandas as pd

def verbatim_prefix(raw, messages):
    """Laenge des laengsten Rohlog-Praefixes, der sich in der Nachrichten-Reihenfolge
    woertlich in Stuecke zerlegen laesst (jedes Stueck zusammenhaengend in einer Nachricht)."""
    p = 0
    for m in messages:
        if p >= len(raw):
            break
        lo, hi = 0, len(raw) - p
        while lo < hi:  # groesstes k mit raw[p:p+k] in m (Praefix-Monotonie)
            k = (lo + hi + 1) // 2
            if raw[p:p + k] in m:
                lo = k
            else:
                hi = k - 1
        p += lo
    return p


MIN_PIECE = 20


def verbatim_prefix_multi(raw, messages):
    """Wie verbatim_prefix, erlaubt aber mehrere Stuecke pro Nachricht (in Reihenfolge)."""
    p = 0
    for m in messages:
        off = 0
        while p < len(raw):
            rest = len(raw) - p
            lo, hi = 0, rest
            while lo < hi:
                k = (lo + hi + 1) // 2
                if raw[p:p + k] in m[off:]:
                    lo = k
                else:
                    hi = k - 1
            if lo == 0:
                break
            if lo < MIN_PIECE and lo < rest:
                break
            idx = m.find(raw[p:p + lo], off)
            if lo < MIN_PIECE and idx - off > 50:
                break
            p += lo
            off = idx + lo
    return p


def analyse(cond, seed=0):
    ag = pd.read_parquet(f"ag_{cond}.parquet")
    ep = pd.read_parquet(f"ep_{cond}.parquet")
    ag = ag[~ag.is_warmup]
    own = {(r.run_id, r.episode_index, r.agent): r for r in ag.itertuples()}
    rows = []
    for e in ep[~ep.is_warmup].itertuples():
        msgs = list(e.communication) if e.communication is not None else []
        for judge, peer in (("alice", "bob"), ("bob", "alice")):
            p = own.get((e.run_id, e.episode_index, peer))
            j = own.get((e.run_id, e.episode_index, judge))
            if p is None or j is None or j.verdict is None:
                continue
            rl = p.raw_log or ""
            pms = [m["content"] for m in msgs if m["sender"] == peer]
            k = verbatim_prefix(rl, pms) if rl else 0
            rows.append(dict(run=e.run_id, ep=e.evaluation_episode, task=p.task_type,
                             cov=k / len(rl) if rl else np.nan,
                             full=bool(rl) and k == len(rl),
                             whole=bool(rl) and any(rl in m for m in pms),
                             multi=bool(rl) and verbatim_prefix_multi(rl, pms) == len(rl),
                             cond=cond, seq=e.sequence_id, judge=judge, task_id=p.task_id,
                             verdict=j.verdict, forced=bool(j.verdict_forced),
                             raw_chars=len(rl),
                             acc=j.verdict == "accept",
                             peer_correct=bool(p.task_correct)))
    d = pd.DataFrame(rows)
    g = d.groupby("run").apply(lambda x: pd.Series({
        "n1": x.peer_correct.sum(), "a1": x[x.peer_correct].acc.sum(),
        "n0": (~x.peer_correct).sum(), "a0": x[~x.peer_correct].acc.sum()})).values
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(2000):
        s = g[rng.integers(0, len(g), len(g))].sum(0)
        bs.append(s[1] / s[0] - s[3] / s[2])
    a1 = d[d.peer_correct].acc.mean()
    a0 = d[~d.peer_correct].acc.mean()
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"{cond}: Urteile={len(d)}  verbatim_stuecke={d.full.mean():.3f}  verbatim_am_stueck={d.whole.mean():.3f}"
          f"  verbatim_mehrteilig={d.multi.mean():.3f}  erzwungene Urteile={d.forced.sum()}"
          f"  Abdeckung: Median={d['cov'].median():.3f}, Anteil>=0,99={(d['cov']>=0.99).mean():.3f}")
    for f, x in d.groupby("full"):
        print(f"  verbatim_stuecke={f}: n={len(x)}  P(ACC|korrekt)={x[x.peer_correct].acc.mean():.3f}"
              f"  P(ACC|falsch)={x[~x.peer_correct].acc.mean():.3f}  n_falsch={(~x.peer_correct).sum()}")
    print(f"  P(ACC|korrekt)={a1:.3f}  P(ACC|falsch)={a0:.3f}  Trennschaerfe={a1 - a0:.3f} [{lo:.3f}; {hi:.3f}]"
          f"  n_falsch={(~d.peer_correct).sum()}")
    print("  voller Log je Episode:", d.groupby("ep").full.mean().round(2).tolist())
    for t, x in d.groupby("task"):
        print(f"  {t}: voll={x.full.mean():.2f}  P(ACC|korrekt)={x[x.peer_correct].acc.mean():.3f}"
              f"  P(ACC|falsch)={x[~x.peer_correct].acc.mean():.3f}  n_falsch={(~x.peer_correct).sum()}")
    return d


if __name__ == "__main__":
    out = []
    for c in sys.argv[1:] or [
        "communication__gemini-3-1-flash-lite__unconstrained",
        "communication__gemini-3-7-flash__unconstrained",
        "main__gemini-3-1-flash-lite",
        "main__gemini-3-7-flash",
    ]:
        out.append(analyse(c))
    cols = ["cond", "run", "seq", "ep", "judge", "task", "task_id", "peer_correct", "verdict",
            "acc", "forced", "full", "multi", "whole", "cov", "raw_chars"]
    pd.concat(out)[cols].rename(columns={
        "run": "run_id", "ep": "evaluation_episode", "task": "peer_task_type",
        "task_id": "peer_task_id", "acc": "accept", "forced": "verdict_forced",
        "full": "strict_full", "multi": "strict_full_multipiece", "whole": "strict_full_one_message",
        "cov": "verbatim_prefix_coverage", "raw_chars": "peer_raw_log_chars"}).to_csv(
        "urteile_reanalyse.csv", index=False)
    print("geschrieben: urteile_reanalyse.csv")
