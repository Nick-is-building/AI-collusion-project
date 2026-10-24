"""Paper figures (plan section 15; A07 task 3), drawn only from results/summaries/verification.json
("figure_data", written by scripts/analysis/verify_all.py). No number is computed or typed here.

  fig1_discrimination   Shi et al.'s 53 conditions, unconstrained and constrained/other as separate groups
  fig2_ladder           detection and false rejection by variant, commissions and omissions side by side
  fig3_distance         R1 (cut), R5-post, R1-live on the 40 R1-live items; false rejection R0 vs R0' (cut)
  fig4_countermeasure   operating points (false rejection, detection): R1/R0', R4, R6, R6s, first and gated
  fig5_study2           slot for Study 2 (not drawn until figure_data.study2 is filled)

Output: paper/figures/<name>.pdf and .png (300 dpi).

  PYTHONPATH=. .venv/bin/python -m scripts.analysis.verify_all     # first, writes verification.json
  PYTHONPATH=. .venv/bin/python -m scripts.analysis.figures
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper" / "figures"
# Categorical slots 1-3 of the dataviz reference palette (validated light mode: CVD and normal-vision
# checks pass; slot 3 is below 3:1 contrast, so every mark carries a direct label or legend entry).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
                     "legend.frameon": False, "pdf.fonttype": 42, "font.family": "DejaVu Sans"})


def _err(c: dict):
    e = c["estimate"]
    return e, [[e - c["ci_low"]], [c["ci_high"] - e]]


def _save(fig, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)
    return [str((OUT / f"{name}.{e}").relative_to(ROOT)) for e in ("pdf", "png")]


def fig1_discrimination(fd: dict):
    s0 = fd["study0"]
    groups = [("unconstrained", "Unconstrained (Gemini)", BLUE),
              ("constrained or other", "Constrained and other conditions (context only)", MUTED)]
    rows = {g: sorted([r for r in s0["conditions"] if r["group"] == g], key=lambda r: r["discrimination"])
            for g, _, _ in groups}
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True,
                             gridspec_kw={"width_ratios": [2.0, max(len(rows[groups[1][0]]) / 8, 3)], "wspace": 0.25})
    for ax, (g, title, col) in zip(axes, groups):
        rs = rows[g]
        x = range(len(rs))
        ax.errorbar(x, [r["discrimination"] for r in rs],
                    yerr=[[r["discrimination"] - r["ci_low"] for r in rs], [r["ci_high"] - r["discrimination"] for r in rs]],
                    fmt="o", ms=3.5, color=col, ecolor=col, elinewidth=1, capsize=0)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_title(title, fontsize=8, color=INK, loc="left")
        if g == "unconstrained":
            names = {"gemini-3-1-flash-lite": "3.1\nFlash-Lite", "gemini-3-7-flash": "3.7\nFlash"}
            ax.set_xticks(list(x), [names.get(r["condition"].split("__")[1], r["condition"].split("__")[1])
                                    for r in rs], fontsize=7)
            for i, r in enumerate(rs):
                ax.annotate(f"{r['discrimination']:.3f}", (i, r["discrimination"]), xytext=(5, 0),
                            textcoords="offset points", va="center", fontsize=7, color=INK)
            ax.set_xlim(-0.6, len(rs) - 0.2)
        else:
            ax.set_xticks([])
            ax.set_xlabel(f"{len(rs)} conditions, sorted by discrimination", color=MUTED)
    axes[0].set_ylabel("Discrimination\nP(ACC | correct) − P(ACC | incorrect)")
    fig.text(0.0, -0.1, f"Shi et al.'s published trajectories, {s0['n_conditions']} conditions; 95% intervals from the "
             f"pre-sprint reanalysis. Median {s0['median']:.3f}, maximum {s0['max']:.3f}.", fontsize=7, color=MUTED)
    return _save(fig, "fig1_discrimination")


def _ladder_panel(ax, block: dict, title: str):
    vs = list(block["detection"])
    fr = block["false_rejection"]
    for i, v in enumerate(vs):
        e, err = _err(block["detection"][v])
        ax.errorbar([i - 0.12], [e], yerr=err, fmt="o", ms=4, color=BLUE, elinewidth=1, capsize=0,
                    label="Detection (error versions)" if i == 0 else None)
        ax.annotate(f"{e:.2f}", (i - 0.12, e), xytext=(-3, 6), textcoords="offset points", fontsize=6.5,
                    color=INK, ha="right")
        key = "R1 (R0')" if v == "R1" else v
        if key in fr:
            e2, err2 = _err(fr[key])
            ax.errorbar([i + 0.12], [e2], yerr=err2, fmt="s", ms=4, color=ORANGE, elinewidth=1, capsize=0,
                        label="False rejection (correct versions)" if i == 0 else None)
            ax.annotate(f"{e2:.2f}", (i + 0.12, e2), xytext=(3, 6), textcoords="offset points", fontsize=6.5,
                        color=INK)
    ax.set_xticks(range(len(vs)), [v.replace(" ", "\n") for v in vs], rotation=0, fontsize=7)
    ax.set_xlim(-0.8, len(vs) - 0.4)
    ax.set_ylim(-0.04, 1.08)
    ax.set_title(title, fontsize=8, color=INK, loc="left")


def fig2_ladder(fd: dict):
    lad = fd["ladder"]
    n_c = lad["commission"]["detection"]["R1"]["n_items"]
    n_o = lad["omission"]["detection"]["R1"]["n_items"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), sharey=True,
                             gridspec_kw={"width_ratios": [len(lad["commission"]["detection"]),
                                                           len(lad["omission"]["detection"])]})
    _ladder_panel(axes[0], lad["commission"], f"Planted commissions ({n_c} items)")
    _ladder_panel(axes[1], lad["omission"], f"Planted omissions ({n_o} items)")
    axes[0].set_ylabel("Share of REJECT verdicts")
    axes[0].legend(loc="center left", fontsize=7)
    fig.text(0.0, -0.13, "R1 = workflow context (cut); its correct-version counterpart is R0'. R6 and R6s: "
             "'first' = model's first verdict, 'gated' = after the gate. 95% cluster bootstrap intervals.\n"
             "R6 on omissions ran on omission versions only, so it has no false-rejection point there.",
             fontsize=7, color=MUTED)
    return _save(fig, "fig2_ladder")


def fig3_distance(fd: dict):
    ds = fd["distance"]
    fig, axes = plt.subplots(1, 2, figsize=(5.6, 2.5), gridspec_kw={"width_ratios": [3, 2]})
    for ax, (key, title, col, mk) in zip(axes, [("detection", f"Detection, {ds['n_items']} R1-live items", BLUE, "o"),
                                                ("false_rejection_cut", "False rejection, correct versions", ORANGE, "s")]):
        names = list(ds[key])
        for i, n in enumerate(names):
            e, err = _err(ds[key][n])
            ax.errorbar([i], [e], yerr=err, fmt=mk, ms=4.5, color=col, elinewidth=1, capsize=0)
            ax.annotate(f"{e:.3f}", (i, e), xytext=(6, 0), textcoords="offset points", va="center", fontsize=7, color=INK)
        ax.set_xticks(range(len(names)), names, fontsize=7)
        ax.set_xlim(-0.5, len(names) - 0.3)
        ax.set_title(title, fontsize=8, color=INK, loc="left")
    axes[0].set_ylim(0.7, 1.02)
    axes[1].set_ylim(-0.01, 0.1)
    axes[0].set_ylabel("Share of REJECT verdicts")
    fig.text(0.0, -0.08, "Note the different y-axis ranges. 95% cluster bootstrap intervals.", fontsize=7, color=MUTED)
    return _save(fig, "fig3_distance")


# Label placement for the crowded commission corner of Fig. 4 (layout only; positions are in points).
LABEL_OFFSET = {("commission", "R1 / R0'"): (-48, -14), ("commission", "R4"): (-30, 8),
                ("commission", "R6 first"): (14, -16), ("omission", "R6 first"): (-4, 6)}


def fig4_countermeasure(fd: dict):
    pts = fd["countermeasure"]["points"]
    style = {"commission": (BLUE, "o"), "omission": (ORANGE, "s")}
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.grid(True, axis="both")
    for err_type in ("commission", "omission"):
        col, mk = style[err_type]
        for p in [q for q in pts if q["error"] == err_type]:
            d, f = p["detection"], p["false_rejection"]
            hollow = "note" in p
            ax.errorbar([f["estimate"]], [d["estimate"]],
                        xerr=[[f["estimate"] - f["ci_low"]], [f["ci_high"] - f["estimate"]]],
                        yerr=[[d["estimate"] - d["ci_low"]], [d["ci_high"] - d["estimate"]]],
                        fmt=mk, ms=5, color=col, mfc="white" if hollow else col, elinewidth=0.8, capsize=0)
            ax.annotate(p["variant"] + (" *" if hollow else ""), (f["estimate"], d["estimate"]),
                        xytext=LABEL_OFFSET.get((err_type, p["variant"]), (5, -9)), textcoords="offset points",
                        fontsize=6.5, color=INK,
                        arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5) if (err_type, p["variant"]) in LABEL_OFFSET and err_type == "commission" else None)
    for err_type, (col, mk) in style.items():
        ax.plot([], [], mk, color=col, label=f"Planted {err_type}s")
    ax.legend(loc="lower right", fontsize=7)
    ax.set_xlabel("False rejection (correct versions)")
    ax.set_ylabel("Detection (error versions)")
    ax.set_xlim(-0.01, None)
    ax.set_ylim(0.4, 1.03)
    fig.text(0.0, -0.11, "* R6 on omissions: false rejection taken from the commission items' correct versions "
             "(not measured on the omission items).\n95% cluster bootstrap intervals in both directions.",
             fontsize=7, color=MUTED)
    return _save(fig, "fig4_countermeasure")


def fig5_study2(fd: dict):
    """Slot for the Study 2 figure (strict_full by episode and arm, plan section 15). Not drawn by A07."""
    if (fd.get("study2") or {}).get("status", "").startswith("slot"):
        return []
    raise NotImplementedError("Study 2 figure: to be added with the Study 2 analysis")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--verification", default=str(ROOT / "results" / "summaries" / "verification.json"))
    a = ap.parse_args(argv)
    fd = json.loads(Path(a.verification).read_text())["figure_data"]
    written = []
    for f in (fig1_discrimination, fig2_ladder, fig3_distance, fig4_countermeasure, fig5_study2):
        written += f(fd)
    for w in written:
        print("wrote", w)
    return written


if __name__ == "__main__":
    main()
