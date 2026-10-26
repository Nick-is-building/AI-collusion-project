# Collusion or Inattention? A Planted-Error Audit of Mutual Acceptance in LLM Agents

Nick Wagner, Independent AI Safety Researcher. AI Collusion Research Sprint (Apart Research), October 2026.

## Summary

Shi et al. (2026) let two LLM agents complete tasks, exchange logs and verify each other's work. When a channel limit makes the required evidence impossible to send, the agents drift into mutual acceptance, which the authors count as collusion. Mutual acceptance is also what a verifier produces when it does not check. This project separates the two readings with a planted-error audit. We replay the verdicts of Gemini 3.1 Flash-Lite from Shi et al.'s published trajectories, plant known errors into the peer's work, and compare detection in the original workflow context with detection of the same item in isolation. Commissions add a visible wrong step to the peer's work; omissions remove one valid record whose source sentence is still visible in the transmitted log. Correct versions of every item measure false rejection, so detection can be separated from a general tendency to reject. A positive control instructs the verifier to accept its peer's work, giving a known case of collusion against which the audit is calibrated.

## Key results

Rates are shares of REJECT verdicts. Δ is the difference in detection between isolation and workflow, with a cluster sign-flip p-value over trajectories. Labels: **preregistered** (test in a tagged preregistration), **fixed before outcomes** (test and analysis committed before any call of that stage), **exploratory** (descriptive, no prior test). Sources: `PN` = [`paper/paper_numbers.md`](paper/paper_numbers.md), `V` = [`results/summaries/verification.json`](results/summaries/verification.json).

| Finding | Numbers | Label | Source |
|---|---|---|---|
| Replay fidelity | 71.4% of original REJECTs re-rejected; 0.8% of matched ACCEPTs rejected | preregistered (fidelity check) | PN §1 |
| Commissions are caught in the workflow and in isolation | 97.7% vs 100%; Δ +0.023, p = 0.12 (109 items, 43 trajectories) | preregistered | PN §2 |
| Omissions are missed more often in the workflow | 64% vs 83%; Δ +0.19, p = 0.007 (50 items, 31 trajectories) | fixed before outcomes | PN §5 |
| Removing earlier episodes, a vigilance sentence or a check instruction restores omission detection | from 64% to 94%, 94% and 92%; each Holm-significant | fixed before outcomes | PN §10, §11 |
| Reward and promise cues | lower omission detection by about 9 points; not significant after Holm | fixed before outcomes | PN §8 |
| Other verifiers on identical contexts | omission detection in the workflow: Gemini 3.8 Flash 85%, Claude Haiku 5.5 100%; Gemini 3.8 Flash's false rejection under the check instruction 41% | exploratory | PN §14, §15 |
| Positive control: instructed agreement | omission detection 65% → 16%; discrimination 0.63 → 0.16; the check instruction restores the colluder too (+0.39); stated reasons disclose the agreement in 41% of collusive acceptances | fixed before outcomes (post hoc control, D43) | V `addendum.a18.primary_48` |

A19 (broader positive control, D44, fixed before outcomes; V `addendum.a19.com_109__om_primary_48`): instructed agreement lowers commission detection from 97.7% to 42% (−0.56), and a softer "benefit of the doubt" agreement lowers commission detection to 52% (−0.46) and omission detection to 16% (−0.49); all three Holm-significant.

Mutual acceptance alone cannot separate collusion from unchecked acceptance; a planted-error discrimination test registers instructed collusion.

## Repository map

| Folder | Content |
|---|---|
| [`assignments/`](assignments/) | Written work assignments given to Claude Code (A01–A19) |
| [`blind_check/`](blind_check/) | Blind human check package: instructions, answers, 20 pairs, hash of the local key |
| [`configs/`](configs/) | Model routes, prices and spend caps |
| [`data/`](data/) | Dataset download script and checksums; derived items, baits, readings and preregistration materials |
| [`devlog/`](devlog/) | Append-only development log, indexed by [`DEVLOG_INDEX.md`](DEVLOG_INDEX.md) |
| [`docs/`](docs/) | Deviations from the plan, rubrics, implementation notes, repository audit |
| [`paper/`](paper/) | Generated paper numbers, results tables and figures |
| [`prior_work/`](prior_work/) | Pre-sprint reanalysis and replay-candidate audit (unchanged originals) |
| [`results/`](results/) | Raw call lines, analysis summaries, token counts, Study 2 run tables |
| [`scripts/`](scripts/) | Launchers, reading aids, analyses and figure scripts, one folder per assignment |
| [`src/`](src/) | Library code: replay contexts and baits, runner, analysis, Study 2 |
| [`tests/`](tests/) | Offline test suite |
| [`third_party/`](third_party/) | Shi et al.'s code as a git submodule |

## Reproduce

**Environment.** Python 3.12 with the full dependency freeze:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
git submodule update --init      # third_party/agent-collusion at commit 5afb2c5
```

**Offline rebuild** of all Study 1 numbers, tables and figures from the committed raw call lines (no API calls):

```bash
PYTHONPATH=. .venv/bin/python -m scripts.analysis.verify_all       # results/summaries/verification.json
PYTHONPATH=. .venv/bin/python -m scripts.analysis.results_tables   # paper/results_tables.md
PYTHONPATH=. .venv/bin/python -m scripts.analysis.paper_numbers    # paper/paper_numbers.md
PYTHONPATH=. .venv/bin/python -m scripts.analysis.figures          # paper/figures/
PYTHONPATH=. .venv/bin/python -m scripts.figures.fig_verifier_transfer
.venv/bin/python -m pytest                                          # offline test suite
```

The Study 2 summaries (`results/summaries/study2_analysis.json`, `results/summaries/study2_a05b_sensitivities.json`) are committed. Recomputing them with `scripts/study2/analyze.py` needs the full trajectories, which are kept locally (see below).

**Data.** Shi et al.'s published trajectories: [SALT-NLP/agent-collusion](https://huggingface.co/datasets/SALT-NLP/agent-collusion) on Hugging Face, revision `2eba8f3`. `.venv/bin/python data/download.py` downloads them to `data/raw/` (git-ignored) and checks them against [`data/checksums.txt`](data/checksums.txt). They are needed to rebuild replay contexts, not to rebuild the numbers.

**Paid API calls.** Only the launchers make paid model calls: the pilot scripts in `scripts/pilot/`, `scripts/main/launch_main.py`, `scripts/main/launch_r1live.py`, the `launch_*.py` scripts in `scripts/a06/` to `scripts/a19/`, and `scripts/study2/launch.py`. Their calls go through the runner or the Study 2 guard, which enforce the spend caps in [`configs/caps.yaml`](configs/caps.yaml) and fail closed. `scripts/a03/r0_bisection.py` uses Gemini's free countTokens endpoint. Keys are read from a local `.env` (template [`.env.example`](.env.example)) with the variables `GEMINI_API_KEY` and `ANTHROPIC_API_KEY`.

**Licenses.** This repository: MIT ([`LICENSE`](LICENSE)). Shi et al.'s code in `third_party/agent-collusion`: MIT, copyright Xinrui Shi, Yanzhe Zhang and Diyi Yang.

## Preregistration and integrity

- Git tags: `prereg-v0` (plan and analysis before any paid call), `prereg-v1` ([`PREREGISTRATION.md`](PREREGISTRATION.md), Study 1 main run), `prereg-v1-r1live` ([`PREREGISTRATION_R1LIVE.md`](PREREGISTRATION_R1LIVE.md)), `prereg-study2` ([`PREREGISTRATION_STUDY2.md`](PREREGISTRATION_STUDY2.md)).
- Every departure from the plan is recorded with its timing and decision maker as D1–D44 in [`docs/deviations.md`](docs/deviations.md).
- Evidence labels: a result is preregistered only if its test is in a tagged preregistration, and fixed before outcomes if its test and analysis code were committed before any call of its stage, even when earlier results motivated that stage. All other results, including every comparison across verifier models, are exploratory and reported descriptively.
- The raw call lines behind every reported Study 1 number are committed in `results/raw/`; [`paper/paper_numbers.md`](paper/paper_numbers.md) lists each number with its source key.
- Study 2 storage: per-call tables, run metadata and checksums are committed under `results/study2/`; the full trajectories are kept locally, and their SHA-256 hashes are committed.

## Prior work disclosure

The reanalysis of Shi et al.'s verdicts ran on 23 October 2026, 12:43–13:36 UTC, before the sprint program began (15:15 UTC at the earliest). The replay-candidate audit ran at 15:37 UTC, after that point. Project plan v2.5 was drafted before the sprint and frozen. Everything from the pilot onward is sprint work. Files and details: [`prior_work/README.md`](prior_work/README.md).

## AI usage

Claude was used to plan and review the work. Claude Code implemented the pipeline and the analyses from written assignments ([`assignments/`](assignments/), [`CLAUDE.md`](CLAUDE.md), [`devlog/`](devlog/)). A more capable Claude model and ChatGPT served as reviewers. All decisions were made by Nick Wagner.

## Citation

Shi, X., Zhang, Y., and Yang, D. (2026). Emergent Collusion in Long-Horizon LLM Agent Interaction. arXiv:2609.24967.

This project:

```bibtex
@misc{wagner2026collusion,
  author = {Wagner, Nick},
  title  = {Collusion or Inattention? A Planted-Error Audit of Mutual Acceptance in LLM Agents},
  year   = {2026},
  note   = {AI Collusion Research Sprint (Apart Research)},
  url    = {https://github.com/Nick-is-building/AI-collusion-project}
}
```

## License

MIT, see [`LICENSE`](LICENSE).
