"""Paper numbers (0 USD): every number the paper may use, one line each, with its exact source key.

Reads only results/summaries/verification.json and the summary files next to it (no raw file, no hand-typed number)
and writes paper/paper_numbers.md. Each row: quantity, source key (file:path), estimate, 95% CI, raw p, Holm p
(where defined), n (items / trajectories, or sequences, or calls), and the item set.

Mechanics: every source JSON is flattened into
  - stat nodes: dicts with "estimate" (Study 1 style: ci_low/ci_high, p, p_holm, n_items, n_clusters) or "mean_d"
    (Study 2 style: ci95_t, ci95_bootstrap {lo, hi}, p_two_sided, n, n_excluded); one row each, not descended into;
  - scalar leaves outside stat nodes (rates, counts, flags, spend); one row each.
List elements are addressed by their identifying fields, e.g. `per_variant[variant=R1,version=bait].reject_rate_items`.
Rows are selected per section by glob patterns over these paths (fnmatch; "*" also matches dots). A pattern that
matches nothing raises an error, so a renamed key is caught (adapt the patterns, never the numbers).

  PYTHONPATH=. .venv/bin/python -m scripts.analysis.paper_numbers
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUMMARIES = ROOT / "results" / "summaries"
OUT = ROOT / "paper" / "paper_numbers.md"
SOURCES = {"V": "verification.json", "S2": "study2_analysis.json", "S2b": "study2_a05b_sensitivities.json",
           "D40": "sensitivity_residue.json", "D42": "d42_accept_classes.json", "P10": "p10_projection.json"}

PREREG = "preregistered main-run set (109 items, 43 trajectories)"
D25ALL = "D25 omission items, all 50 (31 trajectories)"
PRIM48 = "primary 48 (D25 without rep041_e06, rep044_e03)"
ALL50 = "all 50 (sensitivity)"
NO4 = "46, without the 4 D40-flagged items (sensitivity)"
S2SET = "Study 2, 50 sequences (paired)"
EXCL_DEFAULT = ("*missing_as_*",)

# (section title, [(source, include patterns, item-set label, extra excludes)])
SECTIONS = [
    ("1. Reproduction and fidelity (Study 0, P2, levels 1 and 2, cut artifact)", [
        ("V", ["figure_data.study0.*"], "Study 0: Shi et al.'s published trajectories", ("*conditions*",)),
        ("V", ["meta.pilot_P2.*"], "pilot P2: 10 hold-out items, R0", ()),
        ("V", ["confirmatory.prereg_v1.fidelity_level1.*"], "fidelity level 1: R0 calls (main run + fidelity set)", ()),
        ("V", ["confirmatory.prereg_v1.fidelity_level2.*"], "fidelity level 2: 21 original REJECTs, 42 matched ACCEPTs", ()),
        ("V", ["confirmatory.prereg_v1.cut_artifact*"], PREREG, ()),
    ]),
    ("2. Main run: planted commissions, preregistered primary test (prereg-v1)", [
        ("V", ["confirmatory.prereg_v1.n_main_items", "confirmatory.prereg_v1.n_clusters",
               "confirmatory.prereg_v1.primary*", "confirmatory.prereg_v1.per_variant*",
               "confirmatory.prereg_v1.discrimination*", "confirmatory.prereg_v1.draw_agreement*",
               "confirmatory.prereg_v1.missing_sensitivity.*.primary*",
               "confirmatory.prereg_v1.bob_states_condition_sensitivity.primary*",
               "confirmatory.prereg_v1.right_reason[*"], PREREG, ("*missing_sensitivity.*.secondary*",)),
    ]),
    ("3. Main run: preregistered secondaries (Holm over six), R5 equivalence, R6 gate", [
        ("V", ["confirmatory.prereg_v1.secondary*", "confirmatory.prereg_v1.r5_equivalence*",
               "confirmatory.prereg_v1.r6_gate*"], PREREG, ()),
    ]),
    ("4. R1-live (prereg-v1-r1live) and D26 R5-post", [
        ("V", ["confirmatory.prereg_v1_r1live.*"], "R1-live subset (40 items, 26 trajectories)", ("*composition.evaluation_episodes*",)),
        ("V", ["addendum.D26_R5post.*"], "R1-live subset (40 items)", ()),
    ]),
    ("5. D25 planted omissions (incl. D_om and the 22 shared items)", [
        ("V", ["addendum.D25_omission.*"], D25ALL, ("*commission_detection.items_with_omission_version*",)),
        ("V", ["addendum.D25_omission.commission_detection.items_with_omission_version*"],
         "22 shared items (main-list items with a D25 omission version)", ()),
    ]),
    ("6. Countermeasures: R6 (prereg, section 3), R6 on omissions, R6s (D28), R6x (D30), R6 correct (D31)", [
        ("V", ["addendum.D28_R6s.*"], D25ALL, ()),
        ("V", ["addendum.D30_D31_R6x.*"], D25ALL, ()),
    ]),
    ("7. Natural errors: N1/N4 (prereg, descriptive), D24 decidability, A14 NAT", [
        ("V", ["confirmatory.prereg_v1.natural_errors*"], "natural-error set (35 items)", ()),
        ("V", ["confirmatory.natural_by_decidability.*"], "natural-error set (35 items) by D24 class", ()),
        ("V", ["addendum.a14.NAT.*"], "26 natural-error extraction items (21 trajectories)",
         ("*recognise_and_approve.*.calls*", "*records.flagged*")),
    ]),
    ("8. A10: incentive rule (D32), peer signal (D33), named_accept (D34)", [
        ("V", ["addendum.a10.calls", "addendum.a10.missing", "addendum.a10.n_items", "addendum.a10.primary*",
               "addendum.a10.primary_without_bob_states_intent*", "addendum.a10.per_arm.*",
               "addendum.a10.named_accept_reading.n_marker_positive_accepts", "addendum.a10.spend_usd_a10"],
         D25ALL, ()),
    ]),
    ("9. Study 2: H6, H7, secondaries, D35 sensitivities, E1/E2 (exploratory)", [
        ("S2", ["n_runs", "n_seqs", "all_complete", "n_verdict_rows_by_arm.*", "status_line.pass",
                "status_line.n_rows", "status_line.n_failures", "status_line.n_rows_with_mentions_beyond_opening",
                "primary*", "h7*", "secondary.*"], S2SET, ("*excluded_seqs*", "*rewards_B_vs_PC.rows*")),
        ("S2b", ["*"], "Study 2 D35 sensitivities", ("*per_seq*", "*excluded_seqs*")),
        ("V", ["exploratory.a14_study2_evidence.*"], "Study 2, sequences with an incorrect peer task (exploratory)",
         ("*seqs_without_incorrect_peer_task*", "*excluded_seqs*", "*.label", "*.definition", "*.PC_note")),
    ]),
    ("10. A13: omission-version context ladder (D36; Holm over five)", [
        ("V", ["addendum.a13.calls", "addendum.a13.missing", "addendum.a13.n_items", "addendum.a13.primary*",
               "addendum.a13.equivalence*", "addendum.a13.per_variant*", "addendum.a13.draw_agreement*",
               "addendum.a13.spend_usd_a13"], D25ALL, ("*by_episode*",)),
    ]),
    ("11. A14: looking vs. seeing (D37; LOOK, Holm over two)", [
        ("V", ["addendum.a14.LOOK.*", "addendum.a14.spend_usd_a14"], D25ALL, ()),
    ]),
    ("12. A15: history decomposition R3t/R3o (D38; Holm over two)", [
        ("V", ["addendum.a15.calls", "addendum.a15.missing", "addendum.a15.n_items", "addendum.a15.primary*",
               "addendum.a15.secondary.contrasts*", "addendum.a15.secondary.per_variant*", "addendum.a15.spend_usd_a15"],
         D25ALL, ()),
    ]),
    ("13. D40: sensitivities without residue items (post hoc)", [
        ("D40", ["excluded_items*", "excluded_items_genuine*", "table*"],
         "set A = without 4 flagged (46); set B = without 2 genuine residues (48)", ()),
    ]),
    ("14. A16: Gemini 3.8 Flash judging in Flash-Lite's trajectories (D39; Holm over G, H, C)", [
        ("V", ["addendum.a16.calls", "addendum.a16.missing", "addendum.a16.flash_lite_missing",
               "addendum.a16.served_models.only_expected_model", "addendum.a16.spend_usd_a16"], "stage a16", ()),
        ("V", ["addendum.a16.primary_item_set.*"], PRIM48, ()),
        ("V", ["addendum.a16.all_50_sensitivity.primary*", "addendum.a16.all_50_sensitivity.interpretation.rows*"], ALL50, ()),
        ("V", ["addendum.a16.without_all_d40_flagged_sensitivity.primary*",
               "addendum.a16.without_all_d40_flagged_sensitivity.interpretation.rows*"], NO4, ()),
    ]),
    ("15. A17: Claude Haiku 5.5 judging in Flash-Lite's trajectories (D41; Holm over G, H, C; draw 1)", [
        ("V", ["addendum.a17.calls", "addendum.a17.missing", "addendum.a17.spend_usd_a17", "addendum.a17.p6.calls",
               "addendum.a17.p6.submit_verdict_with_thinking", "addendum.a17.p6.passed",
               "addendum.a17.evidence.only_expected_model", "addendum.a17.evidence.calls_with_thinking_in_response",
               "addendum.a17.draw2_dropped", "addendum.a17.draw2_calls_logged_excluded", "addendum.a17.a16_finished"],
         "stage a17", ()),
        ("V", ["addendum.a17.primary_item_set.*"], PRIM48, ()),
        ("V", ["addendum.a17.all_50_sensitivity.primary*", "addendum.a17.all_50_sensitivity.interpretation.rows*",
               "addendum.a17.all_50_sensitivity.haiku_minus_*.contrasts*"], ALL50, ()),
        ("V", ["addendum.a17.without_all_d40_flagged_sensitivity.primary*",
               "addendum.a17.without_all_d40_flagged_sensitivity.interpretation.rows*",
               "addendum.a17.without_all_d40_flagged_sensitivity.haiku_minus_*.contrasts*"], NO4, ()),
    ]),
    ("16. D42: classes of omission ACCEPTs (post hoc, single coder; Wilson intervals over calls)", [
        ("D42", ["cells.*"], PRIM48, ()),
    ]),
    ("17. Spend by stage (USD, our price table)", [
        ("V", ["meta.spend_usd_*"], "all live calls", ()),
        ("P10", ["usd_nocache", "usd_cache"], "P10 projection for the main run (before it ran)", ()),
    ]),
]


def _is_stat(d) -> bool:
    """A single statistic; D40 comparison records (estimate plus estimate_without...) are flattened instead."""
    return isinstance(d, dict) and ("estimate" in d or "mean_d" in d) and "estimate_without" not in d


ID_FIELDS = ("variant", "version", "error_type", "arm", "scope", "test", "judge", "alice_names_bait")


def _is_cmp(d) -> bool:
    """A D40 comparison record: one test, estimated on all items and without each exclusion set."""
    return isinstance(d, dict) and "estimate_without" in d


CMP_SETS = (("", "all 50 items (primary analysis as specified)"), ("_without", "set A: without 4 D40-flagged (46)"),
            ("_without_genuine", "set B: without 2 genuine residues (48)"))


def cmp_rows(d: dict):
    for sfx, label in CMP_SETS:
        if f"estimate{sfx}" not in d:
            continue
        ci = d.get(f"ci{sfx}") or [None, None]
        stat = {"estimate": d.get(f"estimate{sfx}"), "ci_low": ci[0], "ci_high": ci[1], "p": d.get(f"p{sfx}"),
                "p_holm": d.get(f"p_holm{sfx}"), "n_items": d.get(f"n_items{sfx}"),
                "significant": d.get(f"significant{sfx}") if f"significant{sfx}" in d else None}
        yield sfx or "(all)", label, stat


def _elem_id(v, i: int) -> str:
    """List elements are addressed by their identifying fields (e.g. [variant=R1,version=bait]); else by index."""
    if isinstance(v, dict):
        ids = [f"{f}={v[f]}" for f in ID_FIELDS if f in v and not isinstance(v[f], (dict, list))]
        if ids:
            return ",".join(ids)
    return str(i)


def flatten(obj, prefix="") -> dict:
    """path -> stat dict or scalar (stat nodes are not descended into)."""
    out = {}
    if (_is_stat(obj) or _is_cmp(obj)) and prefix:
        out[prefix] = obj
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{_elem_id(v, i)}]"))
    elif obj is None or isinstance(obj, (int, float, bool, str)):
        out[prefix] = obj
    return out


def fmt(x, d=3):
    if x is None:
        return "–"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return f"{x:.{d}f}"
    return str(x).replace("|", "/")


def stat_cells(s: dict) -> tuple[str, str, str, str, str]:
    if "estimate" in s:
        ci = "–" if s.get("ci_low") is None else f"[{fmt(s['ci_low'])}, {fmt(s['ci_high'])}]"
        n = f"{s['n_items']} / {s['n_clusters']}" if "n_clusters" in s else fmt(s.get("n_items"))
        sig = s.get("significant", s.get("significant_holm"))
        holm = fmt(s.get("p_holm"), 4) + ("" if sig is None else f" ({'sig.' if sig else 'n.s.'})")
        return fmt(s["estimate"]), ci, fmt(s.get("p"), 4), holm, n
    t, b = s.get("ci95_t"), s.get("ci95_bootstrap") or {}
    ci = "; ".join(x for x in (f"t [{fmt(t[0])}, {fmt(t[1])}]" if t else "",
                                f"boot [{fmt(b.get('lo'))}, {fmt(b.get('hi'))}]" if b else "") if x) or "–"
    n = f"{s.get('n')} seqs" + (f" ({s['n_excluded']} excl.)" if s.get("n_excluded") else "")
    return fmt(s["mean_d"]), ci, fmt(s.get("p_two_sided"), 4), "–", n


def build(sources: dict, hashes: dict) -> str:
    flat = {k: flatten(v) for k, v in sources.items()}
    lines = ["# Paper numbers", "",
             "Generated by `scripts/analysis/paper_numbers.py` from the summary files only; do not edit by hand. "
             "Each row: estimate, 95% CI (cluster bootstrap over trajectories for Study 1; paired t and sequence "
             "bootstrap for Study 2; Wilson for D42), raw p (cluster sign-flip, or paired t), Holm-adjusted p where a "
             "Holm family exists, n (items / trajectories, sequences, or calls), item set, and the exact source key "
             "(`<file>:<path>`). Rows without an interval are rates, counts, flags or spend. Interpretation is not "
             "part of this file.", "", "Sources:", ""]
    for k, f in SOURCES.items():
        lines.append(f"- `{k}` = `results/summaries/{f}` (SHA-256 `{hashes[k]}`)")
    n_rows = 0
    for title, specs in SECTIONS:
        lines += ["", f"## {title}", "",
                  "| Quantity | Estimate | 95% CI | p (raw) | p (Holm) | n | Item set | Source key |",
                  "|---|---:|---:|---:|---:|---:|---|---|"]
        for src, pats, itemset, excl in specs:
            keys = list(flat[src])
            for pat in pats:
                hit = [k for k in keys if fnmatch.fnmatchcase(k, pat)
                       and not any(fnmatch.fnmatchcase(k, e) for e in tuple(excl) + EXCL_DEFAULT)]
                if not any(fnmatch.fnmatchcase(k, pat) for k in flat[src]):
                    raise KeyError(f"pattern {src}:{pat} matches no key (renamed?)")
                for k in hit:
                    v = flat[src][k]
                    if isinstance(v, str) and len(v) > 60:
                        continue   # labels and notes
                    q = k.split(".", 1)[-1] if "." in k else k
                    if _is_cmp(v):
                        for sfx, label, st in cmp_rows(v):
                            if isinstance(st["estimate"], bool) or st["estimate"] is None or isinstance(st["estimate"], str):
                                est, ci, p, holm, n = fmt(st["estimate"]), "–", "–", "–", "–"
                            else:
                                est, ci, p, holm, n = stat_cells(st)
                            lines.append(f"| {q.replace('|', '/')} {sfx} | {est} | {ci} | {p} | {holm} | {n} | {label} | "
                                         f"`{src}:{k.replace('|', '/')}` (fields estimate{sfx if sfx != '(all)' else ''}...) |")
                            n_rows += 1
                        continue
                    if _is_stat(v):
                        est, ci, p, holm, n = stat_cells(v)
                    else:
                        est, ci, p, holm, n = fmt(v), "–", "–", "–", "–"
                    lines.append(f"| {q.replace('|', '/')} | {est} | {ci} | {p} | {holm} | {n} | {itemset} | "
                                 f"`{src}:{k.replace('|', '/')}` |")
                    n_rows += 1
                keys = [k for k in keys if k not in set(hit)]   # each key once per section
    lines += ["", f"Rows: {n_rows}."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    raw = {k: (SUMMARIES / f).read_bytes() for k, f in SOURCES.items()}
    text = build({k: json.loads(b) for k, b in raw.items()}, {k: hashlib.sha256(b).hexdigest() for k, b in raw.items()})
    Path(a.out).write_text(text)
    print("wrote", a.out, text.count("\n| ") - 2 * len(SECTIONS), "rows")


if __name__ == "__main__":
    main()
