"""paper/results_tables.md from results/summaries/verification.json (A08 task 4).

Every number in the output is read from verification.json (written by scripts/analysis/verify_all.py) and
printed next to its key; nothing is computed here except rounding and joining a key's estimate with its
interval. A key that does not exist raises KeyError, so the tables cannot silently show a stale number.
Groups: confirmatory (prereg-v1, prereg-v1-r1live), addendum (D25, D26, D28, D30, D31, A10 D32-D34, A13 D36), exploratory, and the
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


def a13(t: Tables):
    X = "addendum.a13"
    t.h(3, "3.7 A13 omission-version context ladder R2, R3, R4n, R5 (D36) (50 omission items)")
    if "a13" not in t.get("addendum") or t.get(X).get("status") == "not run":
        t.note("Not run.")
        return
    P = f"{X}.primary"
    keys = ("R2_minus_R1", "R3_minus_R1", "R4_minus_R2", "R5_minus_R4", "R4n_minus_R4")
    t.h(4, "Primary family (Holm over the five contrasts; omission versions)")
    rows = []
    for k in keys:
        r = t.stat_row(f"{t.get(f'{P}.{k}.contrast')} ({t.get(f'{P}.{k}.label')})", f"{P}.{k}")
        rows.append(r[:4] + [t.num(t.get(f"{P}.{k}.p_holm"), 4), t.num(t.get(f"{P}.{k}.significant"))] + r[4:])
    t.table(["Contrast", "Estimate", "95% CI", "p", "p (Holm)", "Significant", "Items / clusters", "Key"], rows)
    t.stats([(f"D for {k} ({'tested' if t.get(f'{P}.D_{k}.tested') else 'not tested, descriptive'})", f"{P}.D_{k}")
             for k in keys])
    t.h(4, "Pre-specified equivalence readings (margin ±0.10)")
    E = f"{X}.equivalence"
    t.values([(f"{k}: CI inside the margin, so '{t.get(f'{E}.{k}.explanation')}' is rejected",
               f"{E}.{k}.explanation_rejected") for k in t.get(E)])
    t.h(4, "Sensitivities of the primary family")
    for sens, lab in (("primary_missing_as_accept", "missing coded ACCEPT"),
                      ("primary_missing_as_reject", "missing coded REJECT")):
        t.stats([(f"{k}, {lab}", f"{X}.{sens}.{k}") for k in keys])
    V = f"{X}.per_variant"
    t.h(4, "Per variant (descriptive, 95% cluster bootstrap CIs)")
    rows = [("R0′: false rejection (correct)", f"{V}.R0p.false_rejection")]
    for v in ("R1", "R2", "R3", "R4", "R4n", "R5"):
        rows.append((f"{v}: detection (omission)", f"{V}.{v}.detection"))
        if "false_rejection" in t.get(f"{V}.{v}"):
            rows += [(f"{v}: false rejection (correct)", f"{V}.{v}.false_rejection"),
                     (f"{v} − R0′ false rejection", f"{V}.{v}.false_rejection_minus_R0p")]
    t.stats(rows)
    vals = []
    for v in ("R1", "R2", "R3", "R4", "R4n", "R5"):
        vals += [(f"{v}: discrimination {t.get(f'{V}.{v}.discrimination_note')}", f"{V}.{v}.discrimination"),
                 (f"{v}: omission REJECTs", f"{V}.{v}.right_reason_deterministic.rejects"),
                 (f"{v}: deterministic right-reason (D25 markers)", f"{V}.{v}.right_reason_deterministic.right_reason"),
                 (f"{v}: right-reason share", f"{V}.{v}.right_reason_deterministic.share")]
    t.values(vals)
    t.h(4, "Detection by evaluation episode (omission; descriptive)")
    for v in ("R1", "R2", "R3", "R4", "R4n", "R5"):
        t.records(f"{V}.{v}.by_episode", ["episode", "items", "detection"])
    t.h(4, "Draw agreement (share of items whose two draws agree)")
    t.values([(f"{k}: agreement", f"{X}.draw_agreement.{k}.agreement") for k in t.get(f"{X}.draw_agreement")])
    t.values([("Calls (stage a13)", f"{X}.calls"), ("Missing verdicts (stage a13)", f"{X}.missing"),
              ("Missing verdicts (reused baselines)", f"{X}.baseline_missing"),
              ("Spend stage a13 (USD)", f"{X}.spend_usd_a13")])


def a15(t: Tables):
    X = "addendum.a15"
    t.h(3, "3.9 A15 history decomposition R3t, R3o (D38; exploratory follow-up of A13) (50 omission items)")
    if "a15" not in t.get("addendum") or t.get(X).get("status") == "not run":
        t.note("Not run.")
        return
    P = f"{X}.primary"
    t.h(4, "Primary family (Holm over H_out and H_work; omission versions)")
    rows = []
    for k in ("H_out", "H_work"):
        r = t.stat_row(f"{k}: {t.get(f'{P}.{k}.contrast')}", f"{P}.{k}")
        rows.append(r[:4] + [t.num(t.get(f"{P}.{k}.p_holm"), 4), t.num(t.get(f"{P}.{k}.significant")),
                             t.num(t.get(f"{P}.{k}.ci_inside_equivalence_margin"))] + r[4:])
    t.table(["Test", "Estimate", "95% CI", "p", "p (Holm)", "Significant", "CI inside ±0.10", "Items / clusters", "Key"], rows)
    t.stats([(f"D for {k} ({'tested' if t.get(f'{P}.D_{k}.tested') else 'not tested, descriptive'})", f"{P}.D_{k}")
             for k in ("H_out", "H_work")])
    t.h(4, "Sensitivities of the primary family")
    for sens, lab in (("primary_missing_as_accept", "missing coded ACCEPT"),
                      ("primary_missing_as_reject", "missing coded REJECT")):
        t.stats([(f"{k}, {lab}", f"{X}.{sens}.{k}") for k in ("H_out", "H_work")])
    S = f"{X}.secondary"
    t.h(4, "Secondary (descriptive, 95% cluster bootstrap CIs)")
    t.stats([(k.replace("_minus_", " − ") + " (omission)", f"{S}.contrasts.{k}") for k in t.get(f"{S}.contrasts")])
    V = f"{S}.per_variant"
    rows = [("R0′: false rejection (correct)", f"{V}.R0p.false_rejection")]
    for v in ("R1", "R3", "R3t", "R3o", "R2"):
        rows.append((f"{v}: detection (omission)", f"{V}.{v}.detection"))
        if "false_rejection" in t.get(f"{V}.{v}"):
            rows += [(f"{v}: false rejection (correct)", f"{V}.{v}.false_rejection"),
                     (f"{v} − R0′ false rejection", f"{V}.{v}.false_rejection_minus_R0p")]
    t.stats(rows)
    t.h(4, "Tokens (API-reported input tokens, omission version) and detection")
    vals = []
    for v in ("R1", "R3", "R3t", "R3o", "R2"):
        o = t.get(f"{V}.{v}")
        if "tokens" in o:
            vals += [(f"{v}: input tokens, median", f"{V}.{v}.tokens.median"),
                     (f"{v}: input tokens, min", f"{V}.{v}.tokens.min"), (f"{v}: input tokens, max", f"{V}.{v}.tokens.max"),
                     (f"{v}: removed tokens vs R1, median", f"{V}.{v}.removed_tokens_vs_R1.median")]
        vals += [(f"{v}: omission REJECTs", f"{V}.{v}.right_reason_deterministic.rejects"),
                 (f"{v}: deterministic right-reason", f"{V}.{v}.right_reason_deterministic.right_reason"),
                 (f"{v}: omission ACCEPTs", f"{V}.{v}.named_accept.accepts"),
                 (f"{v}: named_accept", f"{V}.{v}.named_accept.named_accept")]
    t.values(vals)
    t.records(f"{S}.scatter_detection_vs_removed_tokens.points", ["variant", "median_removed_tokens", "detection"])
    t.values([("Calls (stage a15)", f"{X}.calls"), ("Missing verdicts (stage a15)", f"{X}.missing"),
              ("Missing verdicts (reused baselines)", f"{X}.baseline_missing"), ("Spend stage a15 (USD)", f"{X}.spend_usd_a15")])


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


def a14(t: Tables):
    X = "addendum.a14"
    t.h(3, "3.8 A14 looking vs. seeing (VIG, CHK; D37) and R6x on the natural errors (NAT)")
    if "a14" not in t.get("addendum") or t.get(X).get("status") == "not run":
        t.note("Not run.")
    else:
        L = f"{X}.LOOK"
        if t.get(L).get("status") != "not run":
            P = f"{L}.primary"
            t.h(4, "LOOK primary family (Holm over L1–L2; 50 omission items)")
            rows = []
            for k in ("L1", "L2"):
                r = t.stat_row(f"{k}: {t.get(f'{P}.{k}.contrast')}", f"{P}.{k}")
                rows.append(r[:4] + [t.num(t.get(f"{P}.{k}.p_holm"), 4), t.num(t.get(f"{P}.{k}.significant"))] + r[4:])
            t.table(["Test", "Estimate", "95% CI", "p", "p (Holm)", "Significant", "Items / clusters", "Key"], rows)
            t.stats([(f"D for {k} ({'tested' if t.get(f'{P}.D_{k}.tested') else 'not tested, descriptive'})",
                      f"{P}.D_{k}") for k in ("L1", "L2")])
            for miss in ("accept", "reject"):
                t.stats([(f"{k}, missing coded {miss.upper()}", f"{L}.primary_missing_as_{miss}.{k}") for k in ("L1", "L2")])
            S = f"{L}.secondary"
            t.h(4, "LOOK secondary (descriptive)")
            t.stats([(f"Detection {v}", f"{S}.detection.{v}") for v in ("R1-om", "VIG", "CHK", "R4+VIG", "R4-om", "R6x-first")]
                    + [(f"False rejection {v}", f"{S}.false_rejection.{v}") for v in ("R0p", "VIG", "CHK")]
                    + [("FR(VIG) − FR(R0′)", f"{S}.FR_VIG_minus_R0p"), ("FR(CHK) − FR(R0′)", f"{S}.FR_CHK_minus_R0p"),
                       ("Detection(CHK) − Detection(R6x first)", f"{S}.CHK_minus_R6x_first"),
                       ("Gap under the cue: R4+VIG − VIG", f"{S}.gap_under_cue_R4VIG_minus_VIG"),
                       ("Δ_om: R4-om − R1-om", f"{S}.Delta_om_R4_minus_R1"),
                       ("R4+VIG − R4-om", f"{S}.R4VIG_minus_R4om")])
            t.values([(f"Discrimination {k}", f"{S}.discrimination.{k}") for k in ("VIG", "CHK", "R1_R0p")])
            rows = []
            for k, o in t.get(f"{S}.named_accept_and_right_reason").items():
                key = f"{S}.named_accept_and_right_reason.{k}"
                rows.append([k] + [t.num(o.get(c)) for c in ("calls", "missing", "accepts", "named_accept_calls",
                                                             "rejects", "right_reason_rejects")] + [f"`{key}`"])
            t.table(["Cell", "Calls", "Missing", "Accepts", "Named accepts", "Rejects", "Right-reason rejects", "Key"], rows)
            t.values([(f"Row {k}", f"{L}.interpretation_rows.{k}") for k in t.get(f"{L}.interpretation_rows")
                      if k.startswith("R")] + [("Calls", f"{L}.calls"), ("Missing verdicts", f"{L}.missing")])
        N = f"{X}.NAT"
        if t.get(N).get("status") != "not run":
            t.h(4, "NAT pre-specified test (26 natural-error extraction items; outside the LOOK family)")
            t.stats([("Detection(R6x first) − Detection(N1f)", f"{N}.test_R6x_first_minus_N1f"),
                     ("Detection R6x first", f"{N}.detection_R6x_first"), ("Detection N1f", f"{N}.detection_N1f"),
                     ("Missing as ACCEPT: R6x first − N1f", f"{N}.missing_as_accept.test_R6x_first_minus_N1f"),
                     ("Missing as REJECT: R6x first − N1f", f"{N}.missing_as_reject.test_R6x_first_minus_N1f"),
                     ("Gated detection R6x", f"{N}.gated_detection"), ("Gated R6x − N1f", f"{N}.gated_minus_N1f"),
                     ("Drift: N1f − original N1", f"{N}.drift_N1f_minus_original_N1")])
            t.values([("Significant", f"{N}.significant"), ("Calls", f"{N}.calls"),
                      ("Missing N1f", f"{N}.missing_N1f"), ("Missing R6x first", f"{N}.missing_R6x_first")]
                     + [(f"First-submission compliance: {k}", f"{N}.first_submission_compliance.{k}")
                        for k in t.get(f"{N}.first_submission_compliance")]
                     + [(f"Missing-record label (call × record): {k}", f"{N}.missing_record_labels.per_call_record.{k}")
                        for k in t.get(f"{N}.missing_record_labels.per_call_record")]
                     + [(f"Extra-record label (call × record): {k}", f"{N}.extra_record_labels.per_call_record.{k}")
                        for k in t.get(f"{N}.extra_record_labels.per_call_record")])
            rows = []
            for k, o in t.get(f"{N}.detection_by_call_label_category").items():
                rows.append([k, t.num(o["calls"]), t.num(o["rejects"]), t.num(o["detection"]), t.num(o["items"]),
                             f"`{N}.detection_by_call_label_category.{k}`"])
            t.table(["R6x call label category", "Calls", "First REJECTs", "Detection", "Items", "Key"], rows)
            rows = []
            for by in ("error_type", "d24"):
                for k, o in t.get(f"{N}.detection_by.{by}").items():
                    rows.append([f"{by}: {k}", t.num(o["n_items"]), t.num(o["N1f"]), t.num(o["R6x_first"]),
                                 t.num(o["R6x_final"]), f"`{N}.detection_by.{by}.{k}`"])
            t.table(["Group", "Items", "N1f", "R6x first", "R6x gated", "Key"], rows)
            RA = f"{N}.recognise_and_approve"
            t.values([(f"Reasoning names a missing/extra record among accepts, {v}: {k}", f"{RA}.{v}.{k}")
                      for v in ("N1f", "R6x_first") for k in ("accepts", "names_missing_record", "names_extra_record")]
                     + [(f"R6x first accepts with a missing record labeled include: {k}",
                         f"{RA}.R6x_list_missing_labeled_include_among_first_accepts.{k}")
                        for k in ("accepts", "accepts_with_a_missing_record_labeled_include")]
                     + [(f"Row {k}", f"{N}.interpretation_rows.{k}") for k in t.get(f"{N}.interpretation_rows")
                        if k.startswith("N")])
        t.values([("Spend stage a14 (USD)", f"{X}.spend_usd_a14")])
    E = "exploratory.a14_study2_evidence"
    t.h(3, "4.x A14 task 3: Study 2 evidence value (EXPLORATORY)")
    if "a14_study2_evidence" not in t.get("exploratory"):
        t.note("Not run.")
        return
    t.note(t.get(f"{E}.label"))
    rows = []
    for name, key in (("B − A′", f"{E}.B_vs_Aprime"), ("C′ − A′ (descriptive)", f"{E}.descriptive.Cprime_vs_Aprime"),
                      ("PC − A′, Alice only (descriptive)", f"{E}.descriptive.PC_alice_vs_Aprime_alice")):
        for e in ("E1_p_inc", "E2_disc"):
            o = t.get(f"{key}.{e}")
            ci, bs = o.get("ci95_t") or [None, None], o.get("ci95_bootstrap") or {}
            rows.append([f"{name}: {e}", t.num(o.get("mean_d")), f"[{t.num(ci[0])}, {t.num(ci[1])}]",
                         f"[{t.num(bs.get('lo'))}, {t.num(bs.get('hi'))}]", t.num(o.get("p_two_sided"), 4),
                         f"{o.get('n')} / {o.get('n_excluded')}", f"`{key}.{e}`"])
    t.table(["Contrast", "Mean d", "95% t CI", "95% bootstrap CI", "p (paired t)", "Seqs / excluded", "Key"], rows)
    t.values([("Statement", f"{E}.statement")])

SENSITIVITY = ROOT / "results" / "summaries" / "sensitivity_residue.json"


def d40(t: Tables):
    """D40 residue sensitivity; numbers from results/summaries/sensitivity_residue.json (key `table[i]`)."""
    t.h(2, "5. D40 sensitivity: D25 omission analyses without the residue-flagged items (post hoc)")
    if not SENSITIVITY.exists():
        t.note("Not run.")
        return
    raw = SENSITIVITY.read_bytes()
    v = json.loads(raw)
    t.note(f"Source `results/summaries/sensitivity_residue.json` (SHA-256 `{hashlib.sha256(raw).hexdigest()}`); keys "
           f"refer to that file. Excluded items (residue scan, `data/derived/residue_scan_d25.csv`): "
           f"{', '.join(v['excluded_items'])}. Same code and methods; significance as each analysis defines it "
           "(Holm where a family exists; D only under gatekeeping).")
    rows = []
    for i, r in enumerate(v["table"]):
        ci = lambda c: "–" if not c or c[0] is None else f"[{t.num(c[0])}, {t.num(c[1])}]"
        rows.append([r["test"], t.num(r.get("estimate")), ci(r.get("ci")), t.num(r.get("p_holm") if r.get("p_holm") is not None else r.get("p"), 4),
                     t.num(r.get("significant")), t.num(r.get("estimate_without")), ci(r.get("ci_without")),
                     t.num(r.get("p_holm_without") if r.get("p_holm_without") is not None else r.get("p_without"), 4),
                     t.num(r.get("significant_without")), "CHANGE" if r["significance_changes"] else "",
                     f"`sensitivity_residue.json:table[{i}]`"])
    t.table(["Test / row", "Estimate", "95% CI", "p (Holm if any)", "Significant", "Without flagged",
             "95% CI", "p (Holm if any)", "Significant", "Change", "Key"], rows)

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
    a13(t)
    a14(t)
    a15(t)
    exploratory(t)
    figure_data(t)
    d40(t)
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
