# Paper figures (plan §15; assignment A07 task 3, updated in A08 task 3)

Generated, never edited by hand. Every plotted number comes from `results/summaries/verification.json`
(`figure_data`, written by `scripts/analysis/verify_all.py`); the figure script computes nothing.

```
PYTHONPATH=. .venv/bin/python -m scripts.analysis.verify_all
PYTHONPATH=. .venv/bin/python -m scripts.analysis.figures
```

| File | Content |
|---|---|
| `fig1_discrimination.{pdf,png}` | Discrimination P(ACC\|correct) − P(ACC\|incorrect) in Shi et al.'s 53 conditions; the two unconstrained conditions and all other conditions as separate groups (pre-sprint reanalysis table, SHA-256 checked) |
| `fig2_ladder.{pdf,png}` | Detection and false rejection by variant; planted commissions (main run) and planted omissions (D25, D28, D30, D31) side by side |
| `fig3_distance.{pdf,png}` | R1 (cut), R5-post (D26), R1-live on the 40 R1-live items; false rejection R0 vs R0′ (cut artifact) |
| `fig4_countermeasure.{pdf,png}` | Operating points (false rejection, detection): R1/R0′, R4, R6, R6s, R6x; first and gated verdicts. Since A08 (D31), R6's omission point uses R6's own false rejection on the omission items (no longer the commission items' rate) |
| `fig_verifier_transfer.{pdf,png}` | Verifier transfer (A16/D39, A17/D41; exploratory, descriptive across verifiers): omission detection in R1-om, R4-om, R2-om, R1-om+CHK and false rejection for R0′ and R1+CHK, for Gemini 3.1 Flash-Lite, Gemini 3.8 Flash and Claude Haiku 5.5 (the latter two judging in Flash-Lite's trajectories), primary item set (48 items). Separate script `scripts/figures/fig_verifier_transfer.py`, reading `addendum.a16` / `addendum.a17` of `verification.json` |
| `fig5_study2` | **Slot** for the Study 2 figure (`strict_full` by episode and arm). Not drawn by A07; `figure_data.study2` is a placeholder until the Study 2 analysis adds it |

Intervals: 95% cluster bootstrap (trajectories, 10,000 resamples, seed 2026), except Figure 1 (intervals of the pre-sprint reanalysis).
Colours: categorical slots 1–2 of the dataviz reference palette (blue, orange), validated for colour-vision deficiency; every mark is also labelled.
