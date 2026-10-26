"""Figure: verifier transfer (A16, D39; A17, D41; exploratory, descriptive across verifiers).

Panel A: omission detection in R1-om, R4-om, R2-om and R1-om+CHK; panel B: false rejection on the correct versions
for R0' and R1+CHK. Three verifiers on the identical D25 contexts, primary item set (48 items, 31 trajectories):
Gemini 3.1 Flash-Lite (its own trajectories), Gemini 3.8 Flash and Claude Haiku 5.5 (both judging in Flash-Lite's
trajectories). Points are per-item draw means averaged over items; whiskers are 95% cluster-bootstrap intervals
(trajectories). Haiku cells are single draws (D41 note). No pooling or test across verifiers.
Every number is read from results/summaries/verification.json; nothing is computed here:
  Flash-Lite and 3.8 Flash: addendum.a16.primary_item_set.verifier_comparison.cells.<cell>.{flash_lite, flash_38}
  Haiku:                    addendum.a17.primary_item_set.haiku_minus_flash_lite.cells.<cell>.haiku
The Flash-Lite entries of both blocks must be identical (asserted).

  PYTHONPATH=. .venv/bin/python -m scripts.figures.fig_verifier_transfer
Output: paper/figures/fig_verifier_transfer.pdf and .png (300 dpi).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VERIFICATION = ROOT / "results" / "summaries" / "verification.json"
OUT = ROOT / "paper" / "figures"
# Categorical slots 1-3 of the dataviz reference palette, as in scripts/analysis/figures.py (validated light mode:
# all checks pass; slot 3 below 3:1 contrast, so every series has a legend entry and its own marker shape).
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
VERIFIERS = [  # (label, colour, marker)
    ("Gemini 3.1 Flash-Lite", BLUE, "o"),
    ("Gemini 3.8 Flash (in Flash-Lite's trajectories)", ORANGE, "s"),
    ("Claude Haiku 5.5 (in Flash-Lite's trajectories)", AQUA, "^"),
]
DETECTION = [("R1|omission", "R1-om"), ("R4|omission", "R4-om"), ("R2|omission", "R2-om"),
             ("R1+CHK|omission", "R1-om+CHK")]
FALSE_REJECTION = [("R0p|correct", "R0′"), ("R1+CHK|correct", "R1+CHK")]

plt.rcParams.update({"font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
                     "legend.frameon": False, "pdf.fonttype": 42, "font.family": "DejaVu Sans"})


def series(v: dict) -> dict:
    """cell -> [Flash-Lite, 3.8 Flash, Haiku] entries (estimate, ci_low, ci_high) from verification.json."""
    a16 = v["addendum"]["a16"]["primary_item_set"]["verifier_comparison"]["cells"]
    a17 = v["addendum"]["a17"]["primary_item_set"]["haiku_minus_flash_lite"]["cells"]
    out = {}
    for cell, _ in DETECTION + FALSE_REJECTION:
        if a16[cell]["flash_lite"] != a17[cell]["flash_lite"]:
            raise ValueError(f"Flash-Lite entries differ between addendum.a16 and addendum.a17 for {cell}")
        out[cell] = [a16[cell]["flash_lite"], a16[cell]["flash_38"], a17[cell]["haiku"]]
    return out


def panel(ax, data: dict, cells: list, title: str, ylabel: str):
    offsets = (-0.22, 0.0, 0.22)
    for k, (label, colour, marker) in enumerate(VERIFIERS):
        xs, ys, lo, hi = [], [], [], []
        for i, (cell, _) in enumerate(cells):
            e = data[cell][k]
            xs.append(i + offsets[k])
            ys.append(e["estimate"])
            lo.append(e["estimate"] - e["ci_low"])
            hi.append(e["ci_high"] - e["estimate"])
        ax.errorbar(xs, ys, yerr=[lo, hi], fmt=marker, color=colour, ms=5, lw=1.4, capsize=0, label=label,
                    markeredgecolor="white", markeredgewidth=0.8, zorder=3)
    ax.set_xticks(range(len(cells)), [lab for _, lab in cells])
    ax.set_xlim(-0.6, len(cells) - 0.4)
    ax.set_ylim(0, 1.04)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontsize=8.5, color=INK)
    ax.tick_params(axis="x", length=0)


def build(v: dict, out_dir: Path) -> list[Path]:
    data = series(v)
    n = v["addendum"]["a16"]["primary_item_set"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={"width_ratios": [4, 2.2]})
    panel(a, data, DETECTION, "A  Omission detection (omission versions)", "Share REJECT")
    panel(b, data, FALSE_REJECTION, "B  False rejection (correct versions)", "Share REJECT")
    handles, labels = a.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=7.5, bbox_to_anchor=(0.5, -0.01))
    fig.text(0.01, 0.105, f"Primary item set: {n['n_items']} D25 items, {n['n_clusters']} trajectories. "
                          "Whiskers: 95% cluster-bootstrap intervals. Haiku: one draw per cell.",
             fontsize=6.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.14, 1, 1))
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext in ("pdf", "png"):
        p = out_dir / f"fig_verifier_transfer.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        paths.append(p)
    plt.close(fig)
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--verification", default=str(VERIFICATION))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    for p in build(json.loads(Path(a.verification).read_text()), Path(a.out)):
        print("wrote", p)


if __name__ == "__main__":
    main()
