"""R1-live analysis (PROJECT_PLAN.md 8.4, 8.8; D16, D19; frozen with tag prereg-v1-r1live).

Inputs: the main-run calls frame (for the two R1 bait draws), the R1-live call lines (variant "R1live",
check "R1LIVE"), the bait files, the item meta (cluster = trajectory), the subset of 40, the confirmed
readings (flag B items; Bob's reaction type per item), and the original candidate table.

  primary (D19.1-2): d_i = y(R1-live) - mean of the two R1 draws of item i (y = 1 for REJECT); mean of
    d_i over items with both present; two-sided cluster sign-flip test (10,000 flips, seed 2026) and
    cluster bootstrap CI; alpha 0.05, outside the Holm family. Reported in both directions (H5 open).
  sensitivity (plan 8.4): the same without items with flag A (deterministic) or a confirmed flag B.
  confound rule (D19.4): "conversation erodes detection" is claimed only if the primary estimate is
    negative with p < 0.05 AND, in the subset without flags A and B, the estimate is also negative with
    p < 0.05 ("persists"; operationalization proposed by Claude Code, fixed by the addendum).
    "Conversation rescues detection" (estimate positive) is reported under the same two conditions.
  limited check (plan 8.4): more than a quarter of the 40 items flagged -> R1-live is reported only as a
    limited ecological check.
  intermediate (D19.3): per item (a) Alice names the bait in a live message, (b) Bob's reaction type
    (confirmed reading; keyword type next to it), (c) the R1-live REJECT share per (a, b) cell, with n.
  false-rejection reference (D19.6): the original trajectories' natural verdicts on the correct
    versions of the 40 items (full workflow, all 5 rounds; candidates.csv `verdict`): share REJECT.
  composition (D19.9): task types, trajectories, evaluation episodes, flagged items; reported, never
    changed.
  missing verdicts: excluded pairwise; sensitivity with missing coded as ACCEPT and as REJECT.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.primary import _y, cell, coded, paired, test_contrast
from src.analysis.stats import N_DRAWS, SEED
from src.replay.r1live_screen import screen


def live_frame(records: list[dict], baits: dict) -> pd.DataFrame:
    rows = []
    for r in records:
        s = screen(r, baits[r["item_id"]])
        rows.append(dict(item_id=r["item_id"], verdict_status=r.get("verdict_status"),
                         y=_y(r.get("verdict"), r.get("verdict_status")), **{k: s[k] for k in (
                             "flag_a", "alice_names_bait", "bob_reaction_keyword", "signature_mode")},
                         flag_b_candidate=bool(s["flag_b_candidates"])))
    return pd.DataFrame(rows).set_index("item_id") if rows else pd.DataFrame()


def _decide(primary: dict, unflagged: dict) -> dict:
    def sig(t, sign):
        return t.get("p") is not None and t["p"] < 0.05 and t["estimate"] is not None and np.sign(t["estimate"]) == sign
    return dict(erodes=bool(sig(primary, -1) and sig(unflagged, -1)), rescues=bool(sig(primary, 1) and sig(unflagged, 1)))


def analyze_r1live(main_calls: pd.DataFrame, live: pd.DataFrame, meta: pd.DataFrame, subset: list[str],
                   candidates: pd.DataFrame, confirmed_flag_b: set, confirmed_reaction: dict,
                   n_draws: int = N_DRAWS, seed: int = SEED) -> dict:
    live = live.loc[[i for i in subset if i in live.index]].copy()
    live["flag_b"] = [i in confirmed_flag_b for i in live.index]
    live["flagged"] = live.flag_a | live.flag_b
    live["bob_reaction"] = [confirmed_reaction.get(i) for i in live.index]
    r1 = cell(main_calls[main_calls.item_id.isin(subset)], "R1", "bait")
    out = {}
    for miss in ("exclude", "accept", "reject"):
        y = coded(live, "y", miss)
        d = paired(y, cell(main_calls[main_calls.item_id.isin(subset)], "R1", "bait", missing=miss))
        out[f"primary_missing_{miss}"] = test_contrast(d, meta, n_draws, seed)
    d_all = paired(live.y, r1)
    unflagged = live.index[~live.flagged]
    out["primary"] = out["primary_missing_exclude"]
    out["without_flags"] = test_contrast(d_all.loc[d_all.index.intersection(unflagged)], meta, n_draws, seed)
    out["decision"] = _decide(out["primary"], out["without_flags"])
    n_flag = int(live.flagged.sum())
    out["flags"] = dict(flag_a=int(live.flag_a.sum()), flag_b_confirmed=int(live.flag_b.sum()),
                        flag_b_candidates=int(live.flag_b_candidate.sum()), flagged=n_flag, n=len(live),
                        limited_ecological_check=bool(n_flag > len(subset) / 4))
    cells = []
    for (a, b), g in live.groupby([live.alice_names_bait, live.bob_reaction.fillna("n/a")]):
        cells.append(dict(alice_names_bait=bool(a), bob_reaction=b, n=len(g), n_with_verdict=int(g.y.notna().sum()),
                          reject_share=float(g.y.mean()) if g.y.notna().any() else None))
    out["intermediate"] = cells
    out["detection"] = dict(r1live=float(live.y.mean()) if live.y.notna().any() else None,
                            r1_draw_mean=float(r1.mean()) if len(r1) else None, n_live=int(live.y.notna().sum()))
    c = candidates.set_index("item_id").loc[subset]
    out["false_rejection_reference"] = dict(
        source="original trajectories, correct versions, full workflow (candidates.csv verdict)",
        n=len(c), original_reject=int((c.verdict == "reject").sum()),
        share=float((c.verdict == "reject").mean()))
    out["composition"] = dict(task_types=c.task_type.value_counts().to_dict(), trajectories=int(c.trace.nunique()),
                              evaluation_episodes=c.evaluation_episode.value_counts().sort_index().to_dict(),
                              flagged_items=sorted(live.index[live.flagged]),
                              signature_modes=live.signature_mode.value_counts().to_dict(),
                              missing=int(live.y.isna().sum()))
    return out
