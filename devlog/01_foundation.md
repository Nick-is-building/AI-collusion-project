# DEVLOG 01 — Foundation and provenance

## Scope

Repository initialization, environment and dependencies, original upstream revisions, data intake, baseline reanalysis reproduction, shared technical infrastructure, and provenance of any pre-sprint work. Use this for **implementation records**, not for rewriting the scientific plan.

## Initial state — starter file, not a work entry

No work by Claude Code has been recorded in this block. `PROJECT_PLAN.md` §§3, 6–7, 13–14 identifies pre-sprint research and intended verification tasks. These are descriptions in the plan, **not** independent confirmation that the associated files are present or checks have been reproduced. Record any subsequent verification with actual commands, hashes, outputs and dates.

## Entries (append chronologically below)

<!-- Use the entry format in ../CLAUDE.md. Do not overwrite past entries. -->

## 2026-10-24 ~02:30–04:45 UTC — researcher with planning chat (not Claude Code) — VM and repository setup

**Assignment / authorization:** Done by Nick directly on the VM, guided by the planning chat.
**Built or changed:** System packages updated (`apt upgrade`); boot disk enlarged to 100 GB (96 GB root, about 59 GB free); `gh` and `tmux` installed; Claude Code updated to 2.1.310; `~/collusion-verification-gap/` created with `git init -b main`; repository-local Git identity `Nick-is-building` with GitHub noreply address; `origin` set to `https://github.com/Nick-is-building/AI-collusion-project.git`; repository visibility changed from public to private.
**Decisions:** Repository private until submission; public before submission (plan §11, milestone 6).
**Checks performed:** `gh repo view … --json visibility` returned PRIVATE (reported by Nick). Plan file transferred and checked by size and SHA-256 for version 2.2.1; later replaced by Nick with version 2.5 (not re-hashed in this entry).
**Did not work:** `gh repo edit --accept-visibility-change-consequences` unsupported by the installed `gh`; plain `--visibility private` worked. Claude Code self-update failed without `sudo`; `sudo npm install -g @anthropic-ai/claude-code@latest` worked.
**Evidence / artifacts:** none in the repository.
**State / limitations:** Not checked: whether `origin/main` already contains commits (repository may have been created with a README or license). No Python environment, dataset, or upstream code yet.
**Next:** First Claude Code assignment from the researcher.
**Cross-references:** `CLAUDE.md` (workspace boundary, Git rules, resilience).


## 2026-10-24 05:30–05:55 UTC — Claude Code (Opus 5.5), session A01 — Tasks 0–1: repository state, prereg-v0, environment, upstream, data provenance

**Assignment / authorization:** `assignments/A01_foundation_replay_baits.md` (Nick, 24 Oct 2026), tasks 0 and 1. Authorizes downloads, `.venv` installs, commits/pushes, tag `prereg-v0`. No model API calls.
**Built or changed:**
- First commit `58edd09`: setup files, `PROJECT_PLAN.md`, `prior_work/` as delivered, unmodified. Tag `prereg-v0` (annotated, object `6706997`) → `58edd09`; pushed.
- Merge commit `f7132a6`: `origin/main` already had one commit, `297b70c` "Initial commit" by Nick (20 Oct 2026), containing `LICENSE` (MIT, "Copyright (c) 2026 Nick Wagner") and a one-line `README.md` (`# AI-collusion-project`, no trailing newline). Integrated with `git merge --allow-unrelated-histories`; no force.
- `.venv` (system `/usr/bin/python3.12`, Python 3.12.3). Upstream requirements installed; `litellm==1.94.1` confirmed by `importlib.metadata`.
- `third_party/agent-collusion`: git submodule of `https://github.com/SALT-NLP/agent-collusion`, checked out at `5afb2c595aa3eff6b9b829a032f4f117b36ee54d` (commit date 23 Sep 2026).
- `requirements.txt`: direct dependencies pinned to installed versions; `requirements.lock.txt`: full `pip freeze` (64 lines).
- `data/download.py`: downloads at revision `2eba8f3771e8fbcc0f49f6cbbfd2111b939a117a` (never `main`) into `data/raw/` (git-ignored): `SCHEMA.md`, `EXPERIMENTS.md`, 50 traces of `communication__gemini-3-1-flash-lite__unconstrained`, the 4 agent tables of `pruefsummen_reanalyse.txt`, all 53 episode tables. Checks free disk (≥2 GB) and file counts (50/53). `--verify` recomputes hashes.
- `data/checksums.txt`: SHA-256 of all 109 downloaded files.
- `.gitignore`: added `work/` (local working copies, e.g. unpacked proof package).
**Decisions:** Downloaded all 53 episode tables (16 MB) so the 53-table checksums can be verified; agent tables only for the 4 conditions the reanalysis uses (others not needed by A01).
**Checks performed:**
- Plan header line 9: "design plan, version 2.5 (final for implementation)". SHA-256 of `PROJECT_PLAN.md` = `adf1cca5d8ee880906b2b14fbb276f1ec197d3c0fbbd5ca273aab9bd66a35729` (also verified on the committed blob in `58edd09`).
- SHA-256 of pre-existing evidence in `prior_work/` (never to be edited):
  - `INHALT.md` 6c86ee6720ae10e093151009dbc49cad7f19649aa0d29039436b8af76bd3003a
  - `1_reanalyse/reanalyse_shi.py` 8220b9b1aefe7c6dadfb35362aeec8714805a3683f122679beaf30f1ee9cfd1a
  - `1_reanalyse/nachweispaket_reanalyse.zip` 82d51bded8ce848ce73af66017085423ff3934afa030dc3aa3bd43d2054055fc
  - `1_reanalyse/urteile_reanalyse.csv` 209ebe5164a85081e8d641b1acc558cc47909f1d7c1833ee0728dd185e572779
  - `1_reanalyse/trennschaerfe_alle_bedingungen.csv` e82c737b631ea66c198386c14092b4fe7e65882a239e2d1a7430134bab47609a
  - `1_reanalyse/pruefsummen_reanalyse.txt` 7f8dcc22cd7437c50e5226c2f9c9e18660f971f5b5cad15f09315165c890e5df
  - `2_replay_audit/audit_replay.py` e0af0dca1733c7a62b0c0e1d6a367cdfd884d97180d52e1d380ed9e59d0d7c4a
  - `2_replay_audit/replay_kandidaten.csv` 83e21ac523d1145cae7df1bf6251d0179805b2db714f4b9f67e6bf6ade24d9d9
- **Pre-sprint vs sprint (observed from `prior_work/INHALT.md`, not independently verifiable from file mtimes, which are all 24 Oct 05:13 UTC copy times):** part 1 `1_reanalyse/` = pre-sprint (23 Oct 12:43–13:36 UTC); part 2 `2_replay_audit/` = 23 Oct 15:37 UTC, after the earliest sprint program item (15:15 UTC). Disclosure wording is Nick's decision (plan §18.3).
- Disk: 58 GB free before download; download ≈ 261 MB.
- **Provenance check:** pinned-revision checksums vs. stored ones: 8/8 parquets of `pruefsummen_reanalyse.txt` equal; 53/53 episode tables of `quell_pruefsummen_53_episodentabellen.txt` (from the proof package) equal. ⇒ pre-sprint data (fetched via `resolve/main`) are byte-identical to revision `2eba8f3`. `data/download.py --verify`: "checksums OK".
- Read in full: `data/raw/SCHEMA.md`, `data/raw/EXPERIMENTS.md`. Relevant: `alice_verdict` is Alice's verdict on Bob's task; `raw_log` in agent tables excludes `get_log`; `communication` holds delivered messages in recorded order; `trace_sha256` in runs hashes the gzip; EXPERIMENTS.md lists both-accept 96.2% for our condition.
**Did not work:** First comparison script keyed checksums by basename; agent and episode tables share basenames, so it reported 4 false "differ". A second attempt crashed on the comment line of `pruefsummen_reanalyse.txt`. Third version keyed by full path: all equal. No data issue.
**Evidence / artifacts:** commits `58edd09`, `f7132a6`; tag `prereg-v0`; `data/checksums.txt`; `logs/download.log` (local).
**State / limitations:** Environment working; upstream test suite not run yet. Upstream task resources (`task/`) come from the submodule, not the dataset.
**Next:** Task 2 (Study 0 rerun, candidate audit, figure reproduction, `strict_full` port).
**Cross-references:** plan §§6, 7, 13; DEVLOG_INDEX.

## 2026-10-24 05:36–06:20 UTC — Claude Code (Opus 5.5), session A01 — Task 2: Study 0 rerun, candidate audit, figure reproduction, strict_full port

**Assignment / authorization:** A01 task 2. No API calls.
**Correction to the previous entry:** its header says "05:30–05:55 UTC"; the commit was made at about 05:34 UTC. The work happened 05:24–05:34 UTC.
**Built or changed:**
- `src/replay/traces.py`: trace loader. Episode slicing of the cumulative per-agent message lists; peer `get_log` raw log restricted to the **same episode**; `VerdictContext` per episode and judge; verdict usage entries.
- `src/reanalysis/candidate_audit.py`: independent implementation of the plan §8.1 sampling frame (does not reuse `audit_replay.py`). Prints all task-2 figures. Writes `data/derived/verdict_frame_flash_lite_unconstrained.csv` (Alice, ep ≥ 2, log verbatim in Bob's round-1 message, all task types and correctness; 203 rows).
- `src/reanalysis/transmission.py`: `strict_full`, `strict_full_multipiece`, `verbatim_prefix`, `coverage`, ported from `reanalyse_shi.py`. Logic unchanged; English names.
- `tests/test_transmission.py`: the 60 stored examples, read directly from the committed zip, plus semantics tests. `conftest.py` and `pyproject.toml` add pytest paths.
- Local only (git-ignored `work/`): `work/study0/nachweis/` (unpacked package), `work/study0/regen/` (verdict-table regeneration, parquets symlinked as `ep_`/`ag_`), `work/audit/` (audit rerun).
**Decisions:**
- The audit rerun changed only line 57 (output path `/home/claude/audit/...` → `work/audit/...`); diff verified.
- `reanalyse_shi.py` and `pruefe_alles.py` needed no adaptation; they ran from their working directories.
- In the coverage test, the stored `label_coverage` is rounded to 4 decimals, so the test compares `round(coverage, 4)`. The first run compared at 1e-9 and failed 39/60 for that reason alone. The `strict_full` labels are compared exactly. This is a fixture-precision adjustment, not a criterion change.
**Checks performed (all observed):**
- `sha256sum -c paket_pruefsummen.txt`: 7/7 package files OK.
- `pruefe_alles.py`: checks A–D all OK.
  - A: max 0.155, median 0.053, 0 conditions > 0.20.
  - B: Flash-Lite strict 0.715, false-accept 0.877 (n = 114), ref 0.612; 3.7-Flash 0.687 / 0.945 (n = 109) / 0.638.
  - C: 60/60 agreement.
  - D: Flash-Lite repricing equals recorded cost.
  - Verdict "GESAMT: alle Pruefungen OK".
- Regenerating `urteile_reanalyse.csv` from the pinned parquets gives SHA-256 `209ebe51…72779`, identical to the stored file. Printed: Flash-Lite discrimination 0.107, n_incorrect 152, P(ACC|incorrect) 0.888; 3.7-Flash 0.047, 146, 0.952.
- `urteile_alle_53_bedingungen.csv`: no regeneration script exists in the package. I rebuilt it independently from the 53 pinned episode tables (non-warm-up; judge verdict; peer correctness; scripted = Bob in `controlled_peer`). Result: 53,000/53,000 rows matched on (cond, run_id, evaluation_episode, judge), with 0 mismatches in seq, verdict, peer_correct, scripted_judge.
- `audit_replay.py` rerun on the pinned traces: output CSV byte-identical to the stored `replay_kandidaten.csv` (SHA-256 `83e21ac5…d9d9`). It printed 373 "candidates" and 30 pre-commit matches **before** the episode ≥ 2 and round-1 filters, which the script does not apply. The 168 follow from the CSV filter.
- Stored CSV, filtered (judge alice, ep ≥ 2, round 1, correct, extraction or search): 168 (69 extraction / 99 search), 48 trajectories, max 8 per trajectory, 24 pre_commit, 5 framing_count. Natural-error set 35 (26 / 6 / 3).
- Independent `candidate_audit.py` vs. plan:

| Figure | Plan | Reproduced |
|---|---|---|
| candidates | 168 (69 / 99) | 168 (69 / 99) |
| trajectories, max per trajectory | 48, 8 | 48, 8 |
| median input tokens, original verdict call | 59,830 | 59,829.5 (median of an even n; the two middle values average to .5) |
| max input tokens | 142,648 | 142,648 |
| share > 100k | 12% | 12.5% (21/168) |
| natural-error set | 35: 26 (19 om / 3 com / 4 both), 6, 3 | identical |
| REJECTs in the condition, all judges | 21 | 21 (traces; also 21 in the stored verdict table) |
| correct tasks with complete log, both judges | 601 | 601 (traces via ported `strict_full` on `channel_transcript`; also 601 in the stored table) |
| phrase matches before the cut | 24 | 24 (Alice's own raw log removed before the search, as the audit does; **104 without that removal**) |
| Bob's round-1 message is its own user message starting `[round=1/5][from=bob]`, no round instruction | 168/168 | 168/168, 0 round instructions |
| consecutive user messages | 13 of 168 | see below |

  - Each original verdict call has exactly 1 usage entry, `response_status` accepted.
- **Wording ambiguity in the plan (§§8.2, 22 v2.3, 23.2), recorded, not decided:** the plan says "consecutive user messages occur in 13 of the 168 original verdict calls". The data show something narrower.
  - In 13/168 the message directly before the verdict prompt is Bob's (round-5) message, i.e. "[from=bob] message → verdict prompt", which is the pattern the cut creates.
  - In the other 155, the message before the verdict prompt is Alice's own `send_message` tool result.
  - Consecutive user messages **in general** (Bob's message → round instruction "Use the send_message tool…") occur in 168/168 original verdict contexts.
  - So the plan's conclusion ("not new to the model") holds more strongly than stated. The "13" is correct only for the specific pattern. The replay unit test uses the specific pattern.
- `pytest tests/test_transmission.py`: 62 passed.
**Did not work:**
- First phrase-search run omitted the own-raw-log removal and gave 104; fixed to match the audit definition. This is a definition alignment, documented above.
- First coverage test at 1e-9 tolerance failed on rounding (see Decisions).
**Not verified:** The plan states that all 24 phrase matches were read by hand and are false positives. That is a manual reading claim; I reproduced the count but did not re-read the 24 messages.
**Upstream reading (subagent, read-only, no API calls):**
- No upstream function returns completion kwargs without calling the API. The verdict request is composed from pure helpers: `get_tool_schemas`, `forced_tool_choice`, `get_litellm_completion_kwargs`, `_select_tools_and_choice`, `model_visible_messages`, `with_prose_split_from_tool_calls`, `with_prompt_cache_breakpoint`.
- Stored traces contain no internal markers (`output.py:122` stores `snapshot_visible_messages`).
- **Discrepancy:** the traces contain fields and labels the pinned code at `5afb2c5` does not produce: usage phase `private_outcome_reflection` (code emits `private_reflection`), and `true_expected_verdict`, `evaluator_forced_fail`, `is_warmup`, `evaluation_episode`, `task_order`, `schema_version`. So the dataset was produced by a different code revision or post-processed. The prompts checked so far (system prompt, verdict prompt) match byte for byte. Relevance: request identity (P2) cannot be fully guaranteed from the code pin alone. To be checked in task 4.
- Details are carried into `devlog/03_core_experiment.md` (task 4 entry).
**Evidence / artifacts:** `data/derived/verdict_frame_flash_lite_unconstrained.csv`; local `work/` logs (`work/audit/audit_run.log`, `work/study0/regen/run.log`).
**State / limitations:** Study 0 reproduced; all task-2 figures reproduced except the manual reading claim.
**Next:** Task 3 (item tables).
**Cross-references:** plan §§7, 8.1, 8.2, 23.2; `devlog/03_core_experiment.md`.

## 2026-10-24 06:55 UTC — Claude Code (Opus 5.5), session A02 — Task 4: LICENSE check

**Assignment / authorization:** A02 task 4 (report, do not change).
**Checks performed:** `LICENSE` (from Nick's initial GitHub commit `297b70c`) is the standard MIT License text with "Copyright (c) 2026 Nick Wagner", as plan §14 requires. Not changed. Minor: trailing space after the name.
**Cross-references:** plan §§6, 14; `devlog/03_core_experiment.md` A02 entry.
