# Assignment A01 — Foundation, replay builder, baits (no paid calls)

**Issued by:** Nick Wagner (researcher), 24 October 2026, via the planning chat.
**Governing design:** `PROJECT_PLAN.md` version 2.5 (frozen). Build order: plan §11, steps 1 and 2. Checklist: plan §23.
**Goal:** reach plan milestone 1 (§11) as far as possible without any paid call, and leave the pilot ready to start the moment Nick approves it.

## Authorization

Authorized:
- Everything listed under *Tasks* below, including downloads from GitHub and Hugging Face, installs into `.venv`, commits and pushes per `CLAUDE.md`.
- The tag `prereg-v0` on the first commit that contains `PROJECT_PLAN.md` version 2.5 unchanged (plan §13), pushed to `origin`. Do this before any other work is committed beyond setup files.

Not authorized:
- **Any call to a model API**, paid or free (Gemini, Anthropic, token counting). The pilot (P1–P11) needs a separate approval.
- Any change to `PROJECT_PLAN.md`. If something in the plan is wrong, ambiguous, or impossible, record it in the DEVLOG and report it; do not decide it yourself.
- The tag `prereg-v1`.

Cost caps to configure now (`configs/caps.yaml`): pilot stage 10 USD (plan §12), hard cap 250 USD total. Runners must fail closed when a cap would be exceeded.

## Tasks, in order

Work fast but keep every step tested. Use subagents for parallel work where the parts are independent (for example reading the upstream files in §23.1, or the two bait builders once the item tables exist). Commit and push after each completed task.

### 0. Session start and repository state
- Follow `CLAUDE.md` session-start steps. Confirm the plan header says version 2.5 and record its SHA-256 in `devlog/01_foundation.md`.
- `git fetch origin`. If `origin/main` already has commits (for example a README or license created on GitHub), integrate them with a normal merge (`--allow-unrelated-histories`), never force. Report what was there.
- First commit: setup files (`CLAUDE.md`, DEVLOG, `.gitignore`, `.env.example`, `requirements.txt`, this assignment), `PROJECT_PLAN.md`, and `prior_work/` exactly as delivered (commit message must say the files are pre-sprint or pre-existing and unmodified). Tag `prereg-v0` on it, push commit and tag.

### 1. Environment, upstream code, data
- `.venv` with the system Python 3.12. Shi et al.'s code as a git submodule at `third_party/agent-collusion`, pinned to commit `5afb2c595aa3eff6b9b829a032f4f117b36ee54d`. Install its requirements into `.venv`; confirm `litellm==1.94.1` is what is installed. Update `requirements.txt` with the pinned versions actually used.
- `data/download.py`: download the dataset **at the pinned revision** `2eba8f3771e8fbcc0f49f6cbbfd2111b939a117a` (not `main`) into `data/raw/`: the 50 traces of `communication__gemini-3-1-flash-lite__unconstrained`, `SCHEMA.md`, `EXPERIMENTS.md`, the parquet files listed in `prior_work/1_reanalyse/pruefsummen_reanalyse.txt`, and the 53 episode tables listed in the proof package's `quell_pruefsummen_53_episodentabellen.txt` if Study 0 needs them and disk space allows. Check free disk space first. Write SHA-256 checksums to `data/checksums.txt` and commit that file.
- **Provenance check:** `pruefsummen_reanalyse.txt` says the pre-sprint files were fetched via `resolve/main`, not via the pinned revision. Compare the checksums of the pinned-revision download with the stored ones. Equal: the pre-sprint data are confirmed to match revision `2eba8f3`. Different: stop Study 0, report which files differ; do not mix the two versions.
- Read `SCHEMA.md` and `EXPERIMENTS.md` before parsing traces.

### 2. Pre-sprint work and candidate audit (plan §§3, 7, 8.1)
- `prior_work/` holds the pre-sprint files with their original German names; `prior_work/INHALT.md` lists them. They are preexisting evidence: never edit them, record their SHA-256 in the DEVLOG, and work on copies. Part 1 (`1_reanalyse/`) is pre-sprint; part 2 (`2_replay_audit/`, created 23 October 15:37 UTC) is after the earliest sprint program item. Record this distinction; the disclosure wording is Nick's decision (plan §18.3).
- Study 0 (plan §7): unpack `nachweispaket_reanalyse.zip` into a working copy, rerun `pruefe_alles.py` and the regeneration of the verdict table, compare SHA-256 with the stored values, report check by check. Adapt only paths, never logic; record any adaptation.
- Rerun `audit_replay.py` (it has a hard-coded output path; adapt the path only) on the pinned-revision traces and compare its output with the stored `replay_kandidaten.csv`. Note: the script lists all verdicts with the log in one message; the 168 candidates follow from the CSV with judge = alice, episode ≥ 2, round = 1, correct = True, task type record extraction or data search. The planning chat checked the stored CSV this way: 168 (69 / 99) in 48 trajectories, at most 8 per trajectory, 24 phrase matches, 5 framing counts, natural-error set 35 (26 / 6 / 3). Reproduce this independently.
- Then reproduce the figures that the CSV does not contain from the raw traces:
  - 168 candidates in 48 trajectories; 69 record extraction, 99 data search; at most 8 per trajectory;
  - median input tokens of the original verdict call 59,830, maximum 142,648, 12% above 100,000;
  - natural-error set: 35 candidates (26 extraction with 19 omission, 3 commission, 4 both; 6 data search; 3 code analysis);
  - 21 original REJECT verdicts in the condition (all judges); 601 correct tasks with a complete log (both judges);
  - in all 168 candidates, Bob's round-1 message is its own user message starting with `[round=1/5][from=bob]` and contains no round instruction; consecutive user messages occur in 13 of the 168 original verdict calls.
- **A mismatch is a finding, not a bug to tune away.** Never change a candidate rule to hit a number. Report the exact difference and its cause if found.
- Port `strict_full` (plan §7) into `src/reanalysis/transmission.py` from the pre-sprint code and test it against the 60 stored examples in `stichprobe_uebertragung.jsonl` (plan §23.2). English names in `src/` (plan §14); the originals stay untouched in `prior_work/`.

### 3. Item tables (before any bait or replay output is inspected)
- With seed 2026 and a simple, documented procedure: the pilot hold-out of 20 candidates (8 extraction, 12 data search; plan §8.1), the main candidate list, the natural-error set, and the fidelity set (21 original REJECTs and 42 matched ACCEPTs, plan §8.7). Where the plan does not fix the algorithm, choose one, document it in the DEVLOG, and commit the tables before building anything on them.
- The item table records `correct_counterpart` (R1 → R0′; R2 to R6 → same variant on the correct version), plan §8.4.

### 4. Replay builder, cut, edited histories (build order step 1)
- Read the upstream files listed in plan §23.1 first; log what you learned that affects the build.
- Build Alice's verdict-time context through Shi et al.'s own request builder and memory helpers (plan §23.1 principle). Produce R0 (no cut), the cut context (R0′/R1 base), and the R2, R3, R4, R4n context structures needed for pilot P3 and later steps.
- Unit tests (plan §23.2): byte-identical prefix with thought signatures kept, for all 168 candidates and the fidelity set; no round instruction after the cut; the 13-of-168 consecutive-user-message pattern.
- Dry run: build the exact request kwargs that would be sent, with a mock model, and store request hashes. Whether LiteLLM merges consecutive user messages for Gemini can only be settled in P2/P3; note it as open.

### 5. Pilot harness, ready but not run
- Runner per `CLAUDE.md` and plan §23.2: append-only JSONL, flush per call, resumable by call ID, run IDs, seeds logged, `response_model` logged with stop on change, retries per plan §13, cost tracker from logged usage with the caps above.
- Scripts for pilot checks P1, P2, P3, P9, P10, P11, all passing in dry-run/mock mode. Each script prints the number of calls it would make and its projected cost from the price table (`configs/prices.yaml`, plan §6).

### 6. Baits (build order step 2)
- Extraction baits for all candidates where a valid bait exists (including the hold-out, needed for P11), following plan §8.3 exactly, with automated validation rules 1–3 and a saved diff per item. Then data-search baits against the real SQLite database. Report the item flow (plan §23.4): candidates → baits built → baits validated, per task type.

### 7. Blind check package for Nick (plan §8.3, rule 4)
- 20 random pairs (seed fixed and logged), each pair shuffled. One Markdown file per pair in `blind_check/pairs/`, readable on a tablet in the GitHub web view: only the task information and the transmitted log for both versions, labeled A and B. A form `blind_check/answers_nick.md` where Nick writes, per pair, which version is the bait and what the error is.
- The answer key stays local, outside Git (`blind_check/key.local.json`, already in `.gitignore`). Commit only its SHA-256 now. Nick must not see the key before answering.

### 8. Stop and report
Stop after task 7, or earlier if blocked on everything remaining. If one task is blocked only by something the paid pilot must settle, mark it, and continue with the independent tasks.

Report in under one page:
- verified, not verified, failed (with counts and the reproduced figures from task 2 side by side with the plan's figures);
- the item flow and bait counts;
- anything in the plan that turned out wrong, ambiguous, or impossible;
- readiness of each pilot check and its projected calls and cost;
- whether `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are set in `.env` (set or not set only, never the value);
- commits and tags pushed; spend so far (must be 0 USD).
