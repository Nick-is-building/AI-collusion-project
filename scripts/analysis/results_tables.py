"""paper/results_tables.md from results/summaries/verification.json (A08 task 4).

Every number in the output is read from verification.json (written by scripts/analysis/verify_all.py) and
printed next to its key; nothing is computed here except rounding and joining a key's estimate with its
interval. A key that does not exist raises KeyError, so the tables cannot silently show a stale number.
Groups: confirmatory (prereg-v1, prereg-v1-r1live), addendum (D25, D26, D28, D30, D31, A10 D32-D34), exploratory, and the
descriptive figure data. No interpretation.

  PYTHONPATH=. .venv/bin/python -m scripts.analysis.verify_all
  PYTHONPATH=. .venv/bin/python -m scripts.analysis.results_tables
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFICATION = ROOT / "results" / "summaries" / "verification.json"
OUT = ROOT / "paper" / "results_tables.md"


class Tables:
    def __init__(self, v: dict):
        self.v = v
        self.lines: list[str] = []

    # ------------------------------------------------------------ lookup and formatting
    def get(self, key: str):
        """Key syntax: dot-separated path; list elements as [i]. Keys may contain '-', ' ', '|', "'"."""
        o = self.v
        for part in _split(key):
            o = o[part]
        return o

    @staticmethod
    def num(x, digits=3):
        if x is None:
            return "–"
        if isinstance(x, bool):
            return "yes" if x else "no"
        if isinstance(x, int):
            return str(x)
        if isinstance(x, float):
            return f"{x:.{digits}f}"
        return str(x)

    def stat_row(self, label: str, key: str) -> list[str]:
        """Estimate, 95% CI, p, items/clusters of a dict with 'estimate' (or a scalar)."""
        o = self.get(key)
        if isinstance(o, dict):
            est = o.get("estimate")
            lo, hi = o.get("ci_low"), o.get("ci_high")
            ci = f"[{self.num(lo)}, {self.num(hi)}]" if lo is not None else "–"
            p = self.num(o.get("p"), 4) if "p" in o else "–"
            n = f"{o['n_items']} / {o['n_clusters']}" if "n_clusters" in o else str(o.get("n_items", "–"))
            return [label, self.num(est), ci, p, n, f"`{key}`"]
        return [label, self.num(o), "–", "–", "–", f"`{key}`"]

    # ------------------------------------------------------------ output
    def h(self, level: int, text: str):
        self.lines += ["", "#" * level + " " + text, ""]

    def note(self, text: str):
        self.lines += [text, ""]

    def stats(self, rows: list[tuple[str, str]]):
        self.table(["Quantity", "Estimate", "95% CI", "p", "Items / clusters", "Key"],
                   [self.stat_row(lab, key) for lab, key in rows])

    def values(self, rows: list[tuple[str, str]]):
        self.table(["Quantity", "Value", "Key"], [[lab, self.num(self.get(key)), f"`{key}`"] for lab, key in rows])

    def records(self, key: str, cols: list[str], digits=3):
        """A list of dicts in verification.json, one row per element."""
        rows = []
        for i, r in enumerate(self.get(key)):
            rows.append([self.num(r.get(c), digits) for c in cols] + [f"`{key}[{i}]`"])
        self.table(cols + ["Key"], rows)

    def table(self, head: list[str], rows: list[list[str]]):
        self.lines.append("| " + " | ".join(head) + " |")
        self.lines.append("|" + "|".join("---" if i == 0 or h == "Key" else "---:" for i, h in enumerate(head)) + "|")
        for r in rows:
            self.lines.append("| " + " | ".join(r) + " |")
        self.lines.append("")


def _split(key: str) -> list:
    parts = []
    for seg in key.split("."):
        while "[" in seg and seg.endswith("]"):
            base, idx = seg[:seg.index("[")], seg[seg.index("[") + 1:seg.index("]")]
            if base:
                parts.append(base)
            parts.append(int(idx))
            seg = seg[seg.index("]") + 1:]
        if seg:
            parts.append(seg)
    return parts


# ---------------------------------------------------------------- sections

def confirmatory(t: Tables):
    P = "confirmatory.prereg_v1"
    t.h(2, "1. Confirmatory: prereg-v1 (Study 1, commissions)")
    t.values([("Main items", f"{P}.n_main_items"), ("Trajectories (clusters)", f"{P}.n_clusters")])
    t.h(3, "1.1 Primary contrast and gatekeeping (plan §8.6)")
    t.stats([("Detection R4 (bait)", f"{P}.primary.detection_R4"),
             ("Detection R1 (bait)", f"{P}.primary.detection_R1"),
             ("Δ = R4 − R1", f"{P}.primary.Delta_R4_minus_R1")])
    t.values([("D tested", f"{P}.primary.D.tested"), ("D not tested because", f"{P}.primary.D.reason"),
              ("D, descriptive estimate", f"{P}.primary.D.estimate_descriptive"),
              ("Claim (pre-specified wording)", f"{P}.primary.claim"),
              ("Strong context gap (R4 ≥ 0.70, R1 ≤ 0.30, D > 0)", f"{P}.primary.strong_context_gap")])
    t.h(3, "1.2 Secondary contrasts (Holm over six)")
    rows = []
    for k in t.get(f"{P}.secondary"):
        r = t.stat_row(k, f"{P}.secondary.{k}")
        rows.append(r[:4] + [t.num(t.get(f"{P}.secondary.{k}.p_holm"), 4)] + r[4:])
    t.table(["Contrast", "Estimate", "95% CI", "p", "p (Holm)", "Items / clusters", "Key"], rows)
    t.h(3, "1.3 R5 equivalence view, cut artifact, sensitivities")
    t.stats([("R5 − R4", f"{P}.r5_equivalence.R5-R4"), ("R4 − R5", f"{P}.r5_equivalence.R4-R5"),
             ("R4 − R1", f"{P}.r5_equivalence.R4-R1"),
             ("Cut artifact FR(R0′) − FR(R0)", f"{P}.cut_artifact"),
             ("Δ, missing coded ACCEPT", f"{P}.missing_sensitivity.accept.primary.Delta_R4_minus_R1"),
             ("Δ, missing coded REJECT", f"{P}.missing_sensitivity.reject.primary.Delta_R4_minus_R1"),
             ("Δ, items without the bob_states_condition flag", f"{P}.bob_states_condition_sensitivity.primary.Delta_R4_minus_R1")])
    t.values([("R5 − R4 CI inside ±margin", f"{P}.r5_equivalence.inside_margin"),
              ("Margin", f"{P}.r5_equivalence.margin"),
              ("Cut-artifact mark", f"{P}.cut_artifact.mark"), ("Cut artifact above mark", f"{P}.cut_artifact.above_mark")])
    t.h(3, "1.4 REJECT rates per variant and version (descriptive)")
    t.records(f"{P}.per_variant", ["variant", "version", "calls", "missing", "reject_rate_calls", "items",
                                   "reject_rate_items"])
    t.h(3, "1.5 Discrimination and draw agreement (descriptive)")
    t.values([(f"Discrimination {k} (bait | correct counterpart)", f"{P}.discrimination.{k}")
              for k in t.get(f"{P}.discrimination")]
             + [(f"Draw agreement {k}", f"{P}.draw_agreement.{k}.agreement") for k in t.get(f"{P}.draw_agreement")])
    t.h(3, "1.6 R6 gate (descriptive)")
    g = f"{P}.r6_gate"
    t.values([(f"{ver}: {k}", f"{g}.{ver}.{k}") for ver in ("bait", "correct") for k in t.get(f"{g}.{ver}")]
             + [(f"False rejection {k}", f"{g}.false_rejection_R6_first_vs_R0p.{k}")
                for k in t.get(f"{g}.false_rejection_R6_first_vs_R0p")])
    t.h(3, "1.7 Right-reason detection (deterministic markers; preregistered hand check in §3.2)")
    t.records(f"{P}.right_reason", ["variant", "bait_rejects", "right_reason", "share"])
    t.h(3, "1.8 Detection by evaluation episode (descriptive)")
    t.records(f"{P}.by_episode", ["variant", "episode", "items", "detection"])
    t.h(3, "1.9 Natural-error set N1 / N4 (descriptive)")
    t.records(f"{P}.natural_errors", ["error_type", "items", "detection_N1", "detection_N4", "N4_minus_N1"])
    N = "confirmatory.natural_by_decidability"
    t.values([(f"Overall: {k}", f"{N}.overall.{k}") for k in t.get(f"{N}.overall")]
             + [(f"D24 class {c}: {k}", f"{N}.by_decidability.{c}.{k}")
                for c in t.get(f"{N}.by_decidability") for k in t.get(f"{N}.by_decidability.{c}")])
    t.records(f"{N}.by_error_type_and_decidability", ["error_type", "decidable", "items", "N1_rejects", "N4_rejects",
                                                      "detection_N1", "detection_N4"])
    t.h(3, "1.10 Fidelity (plan §8.7)")
    t.values([(f"Level 1: {k}", f"{P}.fidelity_level1.{k}") for k in
              ("calls", "raw_exact_share", "passes_plan_rule", "storage_adjusted_exact_share", "unexplained_mismatches")]
             + [(f"Level 2: {k}", f"{P}.fidelity_level2.{k}") for k in t.get(f"{P}.fidelity_level2")])

    L = "confirmatory.prereg_v1_r1live"
    t.h(2, "2. Confirmatory: prereg-v1-r1live (40 items)")
    t.stats([("R1-live − R1 (primary)", f"{L}.primary"), ("Without flagged items", f"{L}.without_flags"),
             ("Missing coded ACCEPT", f"{L}.primary_missing_accept"),
             ("Missing coded REJECT", f"{L}.primary_missing_reject")])
    t.values([("Detection R1-live", f"{L}.detection.r1live"), ("Detection R1 (draw mean)", f"{L}.detection.r1_draw_mean"),
              ("Live items", f"{L}.detection.n_live"), ("Decision: erodes", f"{L}.decision.erodes"),
              ("Decision: rescues", f"{L}.decision.rescues")]
             + [(f"Flags: {k}", f"{L}.flags.{k}") for k in t.get(f"{L}.flags")]
             + [(f"False-rejection reference: {k}", f"{L}.false_rejection_reference.{k}")
                for k in ("n", "original_reject", "share")]
             + [(f"Composition: {k}", f"{L}.composition.task_types.{k}") for k in t.get(f"{L}.composition.task_types")]
             + [("Composition: trajectories", f"{L}.composition.trajectories"),
                ("Composition: missing", f"{L}.composition.missing")])
    t.records(f"{L}.intermediate", ["alice_names_bait", "bob_reaction", "n", "n_with_verdict", "reject_share"])


def addendum(t: Tables):
    A = "addendum.D25_omission"
    t.h(2, "3. Addendum (fixed before their own runs; outside the Holm family)")
    t.h(3, "3.1 D25 omission baits (50 items)")
    t.stats([("Detection R1 (omission)", f"{A}.detection_R1_om"), ("Detection R4 (omission)", f"{A}.detection_R4_om"),
             ("Δ_om = R4 − R1", f"{A}.Delta_om_R4_minus_R1"), ("D_om", f"{A}.D_om"),
             ("False rejection R0′", f"{A}.false_rejection_R0p"),
             ("False rejection R4 (correct)", f"{A}.false_rejection_R4_correct"),
             ("Δ_om, missing coded ACCEPT", f"{A}.missing_as_accept.Delta_om_R4_minus_R1"),
             ("Δ_om, missing coded REJECT", f"{A}.missing_as_reject.Delta_om_R4_minus_R1")])
    ci = f"{A}.commission_detection"
    t.values([("Missing verdicts", f"{A}.missing"),
              ("Correct counterparts from the main run", f"{A}.correct_counterparts.from_main_run"),
              ("Correct counterparts from a06", f"{A}.correct_counterparts.from_a06")]
             + [(f"Commission detection, all main items: {k}", f"{ci}.all_main_items.{k}") for k in ("R1", "R4", "n")]
             + [(f"Items with both versions: {k}", f"{ci}.items_with_omission_version.{k}")
                for k in t.get(f"{ci}.items_with_omission_version")]
             + [(f"Natural omissions: {k}", f"{A}.natural_omissions.{k}") for k in ("N1", "N4", "n")]
             + [(f"Right-reason (deterministic) {v}: {k}", f"{A}.right_reason_deterministic.{v}.{k}")
                for v in ("R1", "R4") for k in ("rejects", "right_reason", "share")])
    B = "addendum.D26_R5post"
    t.h(3, "3.2 D26 R5-post (40 R1-live items, descriptive)")
    t.stats([("R5-post − R1", f"{B}.R5post_minus_R1"), ("R5-post − R1-live", f"{B}.R5post_minus_R1live"),
             ("R1-live − R1", f"{B}.R1live_minus_R1")])
    t.values([(f"Detection {k}", f"{B}.detection.{k}") for k in t.get(f"{B}.detection")]
             + [("Missing verdicts", f"{B}.missing"), ("Spend stage a06 (USD)", "addendum.spend_usd_a06")])

    S = "addendum.D28_R6s.R6s"
    t.h(3, "3.3 D28 R6s source enumeration (50 omission items)")
    t.stats([("Detection R6s, first verdict (omission)", f"{S}.detection_R6s_first"),
             ("Detection R1 (omission)", f"{S}.detection_R1"),
             ("R6s first − R1 (pre-specified test)", f"{S}.test_R6s_first_minus_R1_omission"),
             ("Missing coded ACCEPT", f"{S}.missing_as_accept.test_R6s_first_minus_R1_omission"),
             ("Missing coded REJECT", f"{S}.missing_as_reject.test_R6s_first_minus_R1_omission"),
             ("False rejection R6s first", f"{S}.false_rejection_R6s_first"),
             ("False rejection R0′", f"{S}.false_rejection_R0p"),
             ("False rejection R6s first − R0′", f"{S}.false_rejection_R6s_first_minus_R0p"),
             ("Gated detection", f"{S}.gated_final.detection"),
             ("Gated false rejection", f"{S}.gated_final.false_rejection"),
             ("Gated − R1 (omission)", f"{S}.gated_final.final_minus_R1_omission"),
             ("Gated false rejection − R0′", f"{S}.gated_final.false_rejection_final_minus_R0p")])
    t.values([("Significant (α = 0.05)", f"{S}.significant"), ("Calls", f"{S}.calls"),
              ("Missing first verdicts", f"{S}.missing_first")]
             + [(f"Discrimination {k}", f"{S}.discrimination.{k}") for k in t.get(f"{S}.discrimination")]
             + [(f"Gate, {ver}: {k}", f"{S}.gate.{ver}.{k}") for ver in ("omission", "correct")
                for k in t.get(f"{S}.gate.{ver}")]
             + [(f"Removed sentence {k}: {c}", f"{S}.enumeration_completeness.by_listed_removed.{k}.{c}")
                for k in t.get(f"{S}.enumeration_completeness.by_listed_removed") for c in ("calls", "first_rejects")]
             + [(f"Right-reason (deterministic), first REJECTs: {k}", f"{S}.right_reason_deterministic_first.{k}")
                for k in ("rejects", "right_reason")])
    R = "addendum.D28_R6s.R6_omission"
    t.stats([("R6 detection, first verdict (omission)", f"{R}.detection_first"),
             ("R6 detection, gated (omission)", f"{R}.detection_final"),
             ("R6 first − R1 (omission)", f"{R}.first_minus_R1_omission"),
             ("R6 gated − R1 (omission)", f"{R}.final_minus_R1_omission")])
    t.values([(f"R6 gate (omission): {k}", f"{R}.gate.{k}") for k in t.get(f"{R}.gate")]
             + [("Spend stage a07 (USD)", "addendum.D28_R6s.spend_usd_a07")])

    X = "addendum.D30_D31_R6x"
    t.h(3, "3.4 D30 R6x exhaustive source classification (50 omission items)")
    if "D30_D31_R6x" not in t.get("addendum") or t.get(X).get("status") == "not run":
        t.note("Not run.")
        return
    x = f"{X}.R6x"
    t.stats([("Detection R6x, first verdict (omission)", f"{x}.detection_R6x_first"),
             ("Detection R1 (omission)", f"{x}.detection_R1"),
             ("R6x first − R1 (pre-specified test)", f"{x}.test_R6x_first_minus_R1_omission"),
             ("Missing coded ACCEPT", f"{x}.missing_as_accept.test_R6x_first_minus_R1_omission"),
             ("Missing coded REJECT", f"{x}.missing_as_reject.test_R6x_first_minus_R1_omission"),
             ("False rejection R6x first", f"{x}.false_rejection_R6x_first"),
             ("False rejection R0′", f"{x}.false_rejection_R0p"),
             ("False rejection R6x first − R0′", f"{x}.false_rejection_R6x_first_minus_R0p"),
             ("Gated detection", f"{x}.gated_final.detection"),
             ("Gated false rejection", f"{x}.gated_final.false_rejection"),
             ("Gated − R1 (omission)", f"{x}.gated_final.final_minus_R1_omission"),
             ("Gated false rejection − R0′", f"{x}.gated_final.false_rejection_final_minus_R0p")])
    t.values([("Significant (α = 0.05)", f"{x}.significant"), ("Calls", f"{x}.calls"),
              ("Missing first verdicts", f"{x}.missing_first"), ("Missing final verdicts", f"{x}.missing_final")]
             + [(f"Discrimination {k}", f"{x}.discrimination.{k}") for k in t.get(f"{x}.discrimination")])
    t.h(4, "First-submission compliance (gate rule)")
    comp = t.get(f"{x}.first_submission_compliance")
    cols = list(comp["all"])
    t.table(["Group"] + cols + ["Key"],
            [[g] + [t.num(comp[g][c]) for c in cols] + [f"`{x}.first_submission_compliance.{g}`"] for g in comp])
    t.h(4, "Gate outcomes")
    gate = t.get(f"{x}.gate")
    cols = list(next(iter(gate.values())))
    t.table(["Version"] + cols + ["Key"], [[g] + [t.num(gate[g][c]) for c in cols] + [f"`{x}.gate.{g}`"] for g in gate])
    t.h(4, "Detection by the removed sentence's label (first submission; pre-specified group: include)")
    by = t.get(f"{x}.detection_by_removed_sentence_label.by_label")
    cols = ["calls", "first_rejects", "detection", "items", "trajectories"]
    t.table(["Label"] + cols + ["Key"],
            [[k] + [t.num(by[k][c]) for c in cols] + [f"`{x}.detection_by_removed_sentence_label.by_label.{k}`"]
             for k in by])
    t.values([(f"Right-reason (deterministic), first REJECTs: {k}", f"{x}.right_reason_deterministic_first.{k}")
              for k in ("rejects", "right_reason")])
    r = f"{X}.R6_correct"
    t.h(3, "3.5 D31 R6 on the correct versions of the 50 omission items (descriptive)")
    t.stats([("R6 false rejection, first verdict", f"{r}.false_rejection_first"),
             ("R6 false rejection, gated", f"{r}.false_rejection_final"),
             ("R6 first − R0′", f"{r}.false_rejection_first_minus_R0p"),
             ("R6 gated − R0′", f"{r}.false_rejection_final_minus_R0p")])
    t.values([("Calls", f"{r}.calls"), ("Missing first verdicts", f"{r}.missing_first")]
             + [(f"Gate: {k}", f"{r}.gate.{k}") for k in t.get(f"{r}.gate")]
             + [("Spend stage a08 (USD)", f"{X}.spend_usd_a08")])


def a10(t: Tables):
    X = "addendum.a10"
    t.h(3, "3.6 A10 incentive-rule (D32) and peer-signal (D33) arms; named_accept (D34) (50 omission items)")
    if "a10" not in t.get("addendum") or t.get(X).get("status") == "not run":
        t.note("Not run.")
        return
    P = f"{X}.primary"
    t.h(4, "Primary family (Holm over T1–T3; omission versions)")
    rows = []
    for k in ("T1", "T2", "T3"):
        r = t.stat_row(f"{k}: {t.get(f'{P}.{k}.contrast')}", f"{P}.{k}")
        rows.append(r[:4] + [t.num(t.get(f"{P}.{k}.p_holm"), 4), t.num(t.get(f"{P}.{k}.significant"))] + r[4:])
    t.table(["Test", "Estimate", "95% CI", "p", "p (Holm)", "Significant", "Items / clusters", "Key"], rows)
    t.stats([(f"D for {k} ({'tested' if t.get(f'{P}.D_{k}.tested') else 'not tested, descriptive'})", f"{P}.D_{k}")
             for k in ("T1", "T2")])
    t.h(4, "Sensitivities of the primary family")
    for sens, lab in (("primary_missing_as_accept", "missing coded ACCEPT"),
                      ("primary_missing_as_reject", "missing coded REJECT"),
                      ("primary_without_bob_states_intent", "without bob_states_intent items")):
        t.stats([(f"{k}, {lab}", f"{X}.{sens}.{k}") for k in ("T1", "T2", "T3")])
    A = f"{X}.per_arm"
    t.h(4, "Per arm (descriptive, 95% cluster bootstrap CIs)")
    arms = [a for a in t.get(A) if a not in ("R1", "R0p", "secondary_contrasts")]
    rows = [("Detection R1 (omission; a06)", f"{A}.R1.detection"), ("False rejection R0′", f"{A}.R0p.false_rejection")]
    for a in arms:
        rows += [(f"{a}: detection (omission)", f"{A}.{a}.detection"), (f"{a} − R1 (omission)", f"{A}.{a}.minus_R1_omission"),
                 (f"{a}: named_accept (omission)", f"{A}.{a}.named_accept")]
        if "false_rejection" in t.get(f"{A}.{a}"):
            rows += [(f"{a}: false rejection (correct)", f"{A}.{a}.false_rejection"),
                     (f"{a} − R0′ false rejection", f"{A}.{a}.false_rejection_minus_R0p")]
    rows += [(f"Secondary contrast {k} (omission)", f"{A}.secondary_contrasts.{k}") for k in t.get(f"{A}.secondary_contrasts")]
    t.stats(rows)
    vals = []
    for a in arms:
        o = t.get(f"{A}.{a}")
        if "discrimination" in o:
            vals.append((f"{a}: discrimination", f"{A}.{a}.discrimination"))
        vals += [(f"{a}: calls", f"{A}.{a}.calls"), (f"{a}: missing", f"{A}.{a}.missing"),
                 (f"{a}: named_accept calls (omission)", f"{A}.{a}.named_accept_calls_omission"),
                 (f"{a}: marker-positive calls (omission)", f"{A}.{a}.marker_positive_calls_omission")]
        vals += [(f"{a}: 'reward' mentions, {v}", f"{A}.{a}.reward_mention.{v}") for v in o["reward_mention"]]
        vals += [(f"{a}: reciprocity mentions, {v}", f"{A}.{a}.reciprocity_mention.{v}") for v in o["reciprocity_mention"]]
    if "discrimination_R1_R0p" in t.get(f"{A}.R1"):
        vals.append(("R1/R0′: discrimination", f"{A}.R1.discrimination_R1_R0p"))
    t.values(vals)
    t.h(4, "Per arm by Alice's own task correctness (descriptive)")
    for flag in t.get(f"{X}.per_arm_by_alice_correct"):
        B = f"{X}.per_arm_by_alice_correct.{flag}"
        t.values([(f"Alice correct = {flag}: items", f"{B}.n_items")])
        rows = []
        for a in [a for a in t.get(B) if a not in ("R1", "R0p", "secondary_contrasts", "n_items")]:
            rows += [(f"Alice correct = {flag}, {a}: detection", f"{B}.{a}.detection"),
                     (f"Alice correct = {flag}, {a}: named_accept", f"{B}.{a}.named_accept")]
            if "false_rejection" in t.get(f"{B}.{a}"):
                rows.append((f"Alice correct = {flag}, {a}: false rejection", f"{B}.{a}.false_rejection"))
        rows.append((f"Alice correct = {flag}, R1: detection", f"{B}.R1.detection"))
        t.stats(rows)
    t.h(4, "Mentions in the comparison cells (reference)")
    base = t.get(f"{X}.baseline_mentions_comparison_cells")
    t.values([(f"{k}: {m}", f"{X}.baseline_mentions_comparison_cells.{k}.{m}") for k in base for m in base[k]])
    R = f"{X}.named_accept_reading"
    t.h(4, "named_accept reading by Claude Code (D34)")
    t.values([("Marker-positive ACCEPTs", f"{R}.n_marker_positive_accepts")]
             + [(f"Reading {k}: {c}", f"{R}.by_variant_version.{k}.{c}")
                for k in (t.get(R).get("by_variant_version") or {}) for c in t.get(f"{R}.by_variant_version.{k}")])
    t.values([("Items with bob_states_intent (dropped in the sensitivity)", f"{X}.primary_without_bob_states_intent.n_items_dropped"),
              ("Items where Alice's own task is correct", f"{X}.items.alice_correct"),
              ("Calls", f"{X}.calls"), ("Missing verdicts", f"{X}.missing"), ("Spend stage a10 (USD)", f"{X}.spend_usd_a10")])


def recognise_approve(t: Tables):
    E = "exploratory.recognise_and_approve"
    if "recognise_and_approve" not in t.get("exploratory"):
        return
    t.h(3, "4.3 Recognise-and-approve, three separate channels (A10 task 6; exploratory)")
    t.note("Named = a deterministic marker of the planted error (channel 1, reasoning text), the removed sentence in the "
           "verifier's own list (channel 2), or Alice naming the bait in her live messages (channel 3). Caveats in "
           f"`{E}.caveats`.")
    cols = ["source", "variant", "error", "calls", "missing", "accepts", "named_accepts", "not_named_accepts",
            "rejects", "named_rejects"]
    for ch, lab in (("reasoning_text", "Channel 1: reasoning text"), ("verifier_list", "Channel 2: the verifier's own list"),
                    ("r1live_messages", "Channel 3: Alice's live messages (R1-live)")):
        t.h(4, lab)
        t.records(f"{E}.{ch}", cols)


def exploratory(t: Tables):
    E = "exploratory"
    t.h(2, "4. Exploratory (labelled as such)")
    t.h(3, "4.1 Equivalence reading, margin ±0.10")
    rows = []
    for k in t.get(f"{E}.equivalence.contrasts"):
        key = f"{E}.equivalence.contrasts.{k}"
        r = t.stat_row(k, key)
        rows.append(r[:3] + [t.num(t.get(f"{key}.inside_margin"))] + [r[5]])
    t.table(["Contrast", "Estimate", "95% CI", "Inside margin", "Key"], rows)
    t.h(3, "4.2 Right-reason detection by Claude Code reading (preregistered sample and deterministic misses)")
    t.records(f"{E}.right_reason_reading.table", ["scope", "variant", "n", "deterministic", "reading_yes",
                                                  "reading_no", "reading_unclear", "agree"])
    t.values([(f"P11 disclosure: {k}", f"{E}.right_reason_reading.p11_disclosure.{k}")
              for k in t.get(f"{E}.right_reason_reading.p11_disclosure")])
    t.note("D29 (natural-error tension) has no numbers in verification.json; its tables are "
           "`data/derived/rubric/natural_tension_{features,discordant}.csv` and `docs/natural_error_tension.md`.")
    recognise_approve(t)


def figure_data(t: Tables):
    F = "figure_data"
    t.h(2, "5. Descriptive figure data (95% cluster bootstrap intervals)")
    t.h(3, "5.1 Study 0 context (Figure 1)")
    t.values([("Conditions", f"{F}.study0.n_conditions"), ("Median discrimination", f"{F}.study0.median"),
              ("Maximum discrimination", f"{F}.study0.max")])
    rows = []
    for i, c in enumerate(t.get(f"{F}.study0.conditions")):
        if c["group"] == "unconstrained":
            rows.append([c["condition"], t.num(c["discrimination"]), f"[{t.num(c['ci_low'])}, {t.num(c['ci_high'])}]",
                         t.num(c["p_accept_incorrect"]), t.num(c["n_incorrect"]), f"`{F}.study0.conditions[{i}]`"])
    t.table(["Unconstrained condition", "Discrimination", "95% CI", "P(ACC | incorrect)", "n incorrect", "Key"], rows)
    t.h(3, "5.2 Detection and false rejection by variant (Figure 2)")
    for err in ("commission", "omission"):
        for kind in ("detection", "false_rejection"):
            base = f"{F}.ladder.{err}.{kind}"
            t.stats([(f"{err}, {kind.replace('_', ' ')}: {k}", f"{base}.{k}") for k in t.get(base)])
    t.h(3, "5.3 Distance and cut (Figure 3)")
    t.stats([(f"Detection {k}", f"{F}.distance.detection.{k}") for k in t.get(f"{F}.distance.detection")]
            + [(f"False rejection {k}", f"{F}.distance.false_rejection_cut.{k}")
               for k in t.get(f"{F}.distance.false_rejection_cut")])
    t.h(3, "5.4 Countermeasure operating points (Figure 4)")
    rows = []
    for i, p in enumerate(t.get(f"{F}.countermeasure.points")):
        d, f = p["detection"], p["false_rejection"]
        rows.append([p["error"], p["variant"], t.num(d["estimate"]), f"[{t.num(d['ci_low'])}, {t.num(d['ci_high'])}]",
                     t.num(f["estimate"]), f"[{t.num(f['ci_low'])}, {t.num(f['ci_high'])}]",
                     f"`{F}.countermeasure.points[{i}]`"])
    t.table(["Error", "Variant", "Detection", "95% CI", "False rejection", "95% CI", "Key"], rows)


def build(v: dict, source_sha256: str) -> str:
    t = Tables(v)
    t.lines += ["# Results tables (Study 1 and addenda)", "",
                "Generated by `scripts/analysis/results_tables.py` from `results/summaries/verification.json` "
                f"(SHA-256 `{source_sha256}`). Do not edit by hand; rerun the script. Every number is printed "
                "next to its key in verification.json. Rates are shares of REJECT verdicts; per-item cells are "
                "means over an item's draws; intervals are 95% cluster bootstrap (trajectories, 10,000 resamples, "
                "seed 2026); p-values are two-sided cluster sign-flip tests (10,000 draws, seed 2026). "
                "\"Items / clusters\" counts the items with both verdicts and their trajectories. "
                "No interpretation."]
    confirmatory(t)
    addendum(t)
    a10(t)
    exploratory(t)
    figure_data(t)
    return "\n".join(t.lines).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--verification", default=str(VERIFICATION))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    raw = Path(a.verification).read_bytes()
    text = build(json.loads(raw), hashlib.sha256(raw).hexdigest())
    Path(a.out).write_text(text)
    print("wrote", a.out)
    return text


if __name__ == "__main__":
    main()
