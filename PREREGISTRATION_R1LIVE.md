# Preregistration addendum — R1-live (for tag `prereg-v1-r1live`)

**Status: FROZEN, tag `prereg-v1-r1live`.** Prepared by Claude Code under A04 task 4 (D16, D19), 24 October 2026, after P7. Nick Wagner approved it in the Claude Code session on 24 October 2026 (about 11:20 UTC), with three decisions:
1. the relaxed value is added as a data-search marker for "Alice names the bait";
2. "effect persists without flags A and B" means the same sign and p < 0.05 in the unflagged subset;
3. the stage cap `r1live` is 10 USD.

He authorized the tag and the launch on the 40 items after the main run has finished, not in parallel with it. No call on any of the 40 items was made before the tag.

Base: `prereg-v1` (commit `21f4a0f`). That tag froze the 40-item subset (`data/derived/prereg/r1live_subset.csv`, seed 2026) and the plan §8.4 flag rules. This addendum freezes everything else for R1-live. The deviations D16 and D19 (`docs/deviations.md`) are authoritative.

## 1. Question (D19.1)

Two-sided, H5 open: do communication rounds 2–5 erode a detection that succeeds at the decision point, or rescue one that fails? Both directions are reported.

## 2. Driver (D19.5, D19.7; `src/replay/live_driver.py`)

- **Scope:** rounds 2–5 for both agents (Alice first in each round, as upstream), the close of the communication phase, and the verdict phase of both agents. No feedback, no reflection. Channel unconstrained, as in the source condition.
  - Upstream functions are used for the turn mechanics: `_inject_incoming_messages`, `communication_round_instruction`, `_run_agent_attempts`, `deliver_runner_notice`, `_close_communication_phase`, `_open_verdict_phase`, `_record_forced_verdict`.
  - The round loop and the verdict-phase loop are upstream's loop bodies, re-entered at round 2.
  - Model and parameters as in the main run (Gemini 3.1 Flash-Lite, temperature 1.0, reasoning high, max output 64,000, forced tools, 3 attempts per phase turn, 5 API retries).
- **Alice:** her context at the cut is the R1 bait context without the verdict prompt. It is never changed.
  - Hash check (D19.2): the job's `messages_sha256` equals that of the R1 bait request of the same item.
  - P7 verified this against the P11 R1 requests (4/4), and verified the prefix of Alice's first live request (4/4).
- **Bob:** his stored message list up to the tool result of his round-1 `send_message`, made consistent with the bait. Every task-phase tool call matching a log entry gets the bait log's arguments and result, the `get_log` result carries the bait raw log, and the round-1 `send_message` carries the bait message (`chars_sent` updated).
  - JSON strings are re-serialized with the serializer that reproduces the original exactly.
  - Checks per item: the log read back equals the bait raw log; Alice's view equals the bait message. All 40 subset items pass offline (`tests/test_live_driver.py`).
  - Bob's thought signatures are kept.
- **Fallback (D19.5), fixed now:** if the API rejects one of Bob's requests with a 4xx error other than 429, the item restarts from the cut with Bob's signatures removed from the modified turns (`strip_modified`). If that is also rejected, the restart uses signatures removed from all of Bob's current-episode assistant turns (`strip_episode`). If that is rejected too, the item is recorded as missing.
  - Removal cuts the `__thought__` suffix from tool-call IDs (and the matching `tool_call_id`) and drops `provider_specific_fields`.
  - Alice's context is identical in every attempt. Every attempt and its mode are logged.
  - P7: the fallback was not needed (mode `keep` in 4/4).
- **Launcher:** `scripts/main/launch_r1live.py`: 40 items, check `R1LIVE`, stage `r1live`, 4 workers. One run per item (one draw).

## 3. Outcomes and analysis (`src/analysis/r1live.py`)

- **Primary (D19.2):** d_i = y(R1-live) − mean of the two main-run R1 bait draws of item i (y = 1 for REJECT).
  - The mean is taken over items where both are present.
  - Two-sided cluster sign-flip test over trajectories (10,000 flips, seed 2026), cluster bootstrap 95% CI, α = 0.05, outside the Holm family.
  - Missing verdicts are excluded pairwise, with sensitivity analyses coding missing as ACCEPT and as REJECT.
- **Flags (plan §8.4, frozen in prereg-v1; operationalized in `src/replay/r1live_screen.py`):**
  - **Flag A (deterministic):** a live message of Bob's contains every ID or key of his original final answer and not the bait ID or added key.
  - **Flag B:** keyword candidates (`FLAG_B_KEYWORDS`) in Bob's live messages, then a confirming reading. Bob states that he did not select or include the bait record, or denies a step his manipulated log shows. A natural concession is not an artifact.
  - Flags are recorded without repair.
  - Sensitivity analysis: the primary analysis without flagged items.
  - More than a quarter flagged (more than 10 of 40): R1-live is reported only as a limited ecological check.
- **Confound rule (D19.4):** "conversation erodes detection" is claimed only if the primary estimate is negative with p < 0.05 **and** the estimate in the subset without flags A and B is also negative with p < 0.05.
  - "Persists" is operationalized this way; Nick approved it (decision 2).
  - "Rescues" is symmetric. Otherwise no directional claim is made.
- **Intermediate outcomes (D19.3):**
  - (a) Alice names the bait in a live message: a deterministic, case-insensitive, whitespace-normalized match.
    - Extraction: the bait record ID or bait sentence.
    - Data search: the added key, the relaxed condition, **or the relaxed literal** (`added_value` without quotes; clarification after P7, approved by Nick, decision 1).
  - (b) Bob's reaction type to the first bait-naming message of Alice: his first live message in the same or a later round.
    - The keyword type comes from `CONCEDE_KEYWORDS` and `DENY_KEYWORDS`: concede, deny, mixed, ignore, or none.
    - The final type (concede / deny / ignore) is set by a confirming reading.
  - (c) The R1-live REJECT share per (a) × (b) cell, with n.
- **False-rejection reference (D19.6):** the original trajectories' natural verdicts on the correct versions of the 40 items. These are the full workflow with all 5 rounds, from `candidates.csv` `verdict`, reported as the share REJECT. No new calls.
- **Composition (D19.9):** task types, trajectories, evaluation episodes, flagged items, signature modes, and missing verdicts. Reported, never changed.
- **Confirming readings (D19.8)** are done by Claude Code and reported as such. A reading confirms or rejects a keyword candidate and sets the final reaction type. It never changes a deterministic flag or a verdict.

## 4. Keyword lists (D19.8)

The lists in `src/replay/r1live_screen.py` (`FLAG_B_KEYWORDS`, `CONCEDE_KEYWORDS`, `DENY_KEYWORDS`) were drafted before the P7 output was read. They were extended once after reading the 4 P7 transcripts; the additions are marked "P7" in the file:

> "absolutely right", "absolutely correct", "mistake on my part", "made a mistake", "mistakenly included", "clear error", "i understand and accept"

They are fixed from the tag on.

## 5. P7 findings that bear on the rules (pilot, hold-out items)

- **Run:** 4 hold-out items (rep002_e03, rep032_e07 extraction; rep030_e08, rep035_e06 data search; seed 2026).
  - 4/4 complete, 10 API requests each, 0 errors.
  - `response_model` constant.
  - 0.383 USD.
  - Details in `devlog/02_pilot.md`, A04 P7 entry; screen in `results/summaries/p7_screen.json`.
- **Flags:** flag A 0/4; flag B candidates 0/4.
  - By the confirming reading, every Bob reaction was a natural concession: "You are right… I mistakenly included…", or "a mistake on my part".
  - No contradiction about what Bob did was seen.
- **Clarification for (a), approved by Nick (decision 1):**
  - In rep030_e08, Alice named the bait by its relaxed date only ("You used '2025-07-09' as the end date"). The three plan markers (added key, full relaxed condition) miss this.
  - Adopted: the relaxed literal (`added_value` without quotes) is a data-search marker (`MARKER_RELAXED_LITERAL = True`).
  - Risk: a categorical value (e.g. "infection") could also occur in Alice's discussion of her own task. This is accepted as a small false-positive risk.
- **No change to flag A or flag B is proposed.**

## 6. Cost and cap

- P7 measured 0.096 USD per item, so 40 items ≈ 3.8 USD.
- The fail-closed projection without cache is 8.2 USD (`launch_r1live --plan`).
- Stage cap `r1live`: **10 USD** (`configs/caps.yaml`; Nick, decision 3). Hard cap 250 USD unchanged.

## 7. Hashes

SHA-256 of the files this addendum freezes, at the tagged commit:
- `src/replay/live_driver.py`: `539dd11599abb9aa38332b68f7a05fa06f9e677fbe7f382d65438ce520731892`
- `src/replay/r1live_screen.py`: `48add5f5792c720c209b5911bdf2ff44aa861990b1f72d50107d42f27c03eebd`
- `src/analysis/r1live.py`: `2d603b61993ec967a960c90cd0f697869df8afcfe8eb65573643f5963a317f62`
- `scripts/main/launch_r1live.py`: `9688cb83e8b715d8f5aa2ab47bbfe12909391baf6f4f626defdca216f07ce8e1`
- `src/runner/jobs.py`: `33efb11c4df258c4992f9bb6f2d425c4302ac0b1521fc4bc07e56209ba5586d6`
- `configs/caps.yaml`: `9788b449905f877bba752de8622aaafd1586b4d6457134db2f3635e7bc008853`
- `data/derived/prereg/r1live_subset.csv`: `14ee06196ac7dd03b5bb4083ec2cf3d64debd2ec0dfce5582fa4182de6078132`
