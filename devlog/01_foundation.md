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
