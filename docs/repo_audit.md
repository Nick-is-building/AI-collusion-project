# Repository audit before publication (2026-10-26)

Read-only audit of every tracked file at `origin/main` `55fa4fd`, done in a separate worktree (branch `repo-cleanup`). Untracked local files (`.venv/`, `data/raw/`, `logs/`, `results/requests/`, `work/`, `scratch/`, `blind_check/key.local.json`, Study 2 full trajectories) were not part of the audit; they are already git-ignored.

Method: `git ls-files` (1,195 entries) checked for caches, compiled files, editor/OS files, temp/scratch/backup names, logs, empty files and oversized files; every tracked file outside `results/raw/`, the Study 2 run folders, the bait JSON files, `blind_check/pairs/`, `src/`, `scripts/`, `tests/`, `assignments/`, `devlog/` and `prior_work/` was checked for at least one reference by name (or by file stem for figures) from another tracked file.

## (a) Junk that can go

None found. No `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.DS_Store`, editor swap/backup files, `*.tmp`, logs, scratch files or duplicate outputs are tracked. The only empty tracked files are the `__init__.py` package markers in `src/` and `scripts/`, which are required for `python -m scripts...` imports. Git does not track empty directories. Nothing was removed.

`.gitignore` was extended with common editor, OS, Python tooling and temp patterns so that such files cannot be added later by accident.

## (b) Files that stay (research records)

- Design and governance: `PROJECT_PLAN.md` (v2.5, frozen), `PREREGISTRATION.md`, `PREREGISTRATION_R1LIVE.md`, `PREREGISTRATION_STUDY2.md` (tags `prereg-v0`, `prereg-v1`, `prereg-v1-r1live`, `prereg-study2`), `docs/deviations.md`, `docs/*.md`, `CLAUDE.md`, `assignments/`, `devlog/`, `DEVLOG_INDEX.md`.
- Pre-sprint work: `prior_work/` (original files unchanged; checksums and the zip stay valid).
- Blind check: `blind_check/` (instructions, answers, 20 pairs, key hash).
- Data: `data/download.py`, `data/checksums.txt`, `data/derived/` (baits, omission baits, item lists, prereg materials, rubric readings, residue scan, contexts).
- Results: `results/raw/*.jsonl` (all committed call lines), `results/summaries/*.json` (verification and verdict outputs), `results/token_counts/counts.jsonl`, `results/study2/` (P8 and main-run tables, metadata, checksums, superseded C′ attempts).
- Paper: `paper/paper_numbers.md`, `paper/results_tables.md`, `paper/figures/`.
- Code and tests: `src/`, `scripts/`, `tests/`, `conftest.py`, `configs/`, `pyproject.toml`, `requirements.txt`, `requirements.lock.txt`, `.env.example` (variable names only).
- Upstream: `third_party/agent-collusion` (git submodule at `5afb2c5`, MIT license of Shi, Zhang and Yang), `.gitmodules`.
- `LICENSE` (MIT).

## (c) Unclear items (left untouched, for Nick)

1. `results/study2/main/WORKERS` (content `6`): the scheduler's live worker-count control file, written by `scripts/study2/worker_ramp.py` and committed with the export in `650cbae`. It is run state rather than evidence; harmless but not needed to reproduce anything.
2. `prior_work/INHALT.md` states that the German file names will be renamed to English (plan §14). The current instruction keeps the original names so that the checksums and the zip remain valid; `prior_work/README.md` now gives the English description instead. The note in `INHALT.md` is therefore outdated but was not edited.
3. `CLAUDE.md`, `devlog/` and `DEVLOG_INDEX.md` contain local working details (home-directory path `~/collusion-verification-gap`, remote work over SSH from a tablet, a time-zone note). They are research records and were kept; check whether any of this should not be public.
4. `paper/paper_numbers.md` does not yet contain sections for A18 and A19 (both are in `verification.json` and `paper/results_tables.md`); the README cites `verification.json` for them. Before the A19 commit, its `verification.json` hash also differed from the one in `paper/results_tables.md`; after `1f2657c` both cite the same hash. Not changed here.
5. `results/study2/p8/` commits full P8 trajectories (`run.json.gz`, `llm_usage.jsonl`, `bob_cache/`), while the main run keeps them local (D27 storage rule). Consistent with the history (P8 predates D27), noted only for completeness.
