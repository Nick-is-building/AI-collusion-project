# Study 2 — relaunch of the 32 failed C′ arms (option a), decided by Nick, 25 October 2026
The diagnosis entry of 2026-10-24 (devlog/04_hysteresis.md) applies. No Study 2 outcome has been computed or viewed; keep it that way until task 4.
Nick confirms: the AI Studio spend cap has at least 100 USD of headroom above current spend.
## Decision (record as the next free D number in docs/deviations.md before any relaunch)
- Rerun only C′ of rep014–rep045, all 32 fresh (episodes 1–10), including rep014–rep017, whose partial pre-cap attempts are not resumed. Deviation from PREREGISTRATION_STUDY2 §6 and plan §9.2 (all arms rerun). Cause: AI Studio spend-cap 429, outcome-independent; the failure set was fixed by queue position. Prefix, A′, B and PC of these sequences stay as they are.
- Superseded evidence: move every run subdirectory under results/study2/main/repNNN/Cprime/ for NNN 014–045 to results/study2/main_superseded/repNNN/Cprime/ (same relative paths). Nothing is deleted. scheduler.jsonl stays append-only. The export runs on both groups so the superseded attempts keep manifest and hashes in git.
- Relaunch with --reset-attempts "<reason>", group main, seqs 14–45, backend live, stage study2. Workers: 6 while another session runs live calls, 8 only if nothing else runs; never ramp up while any 429 occurs.
- Fail-closed stops (technical change to a provenance path; commit before launch; record in the run metadata): the watcher writes the STOP file if any log line contains "spending cap", or if more than 10 quota 429s occur within 5 minutes. Single transient quota 429s keep upstream's retry.
- Fixed now, before relaunch, in addition to the preregistered primary on all 50 pairs: (1) the primary B − C′ test on the 18 sequences not rerun (rep001–013, rep046–050); (2) C′-only drift check: mean strict_full episodes 6–8, rerun C′ (32) versus original C′ (18), difference with sequence bootstrap CI, descriptive; (3) the B→C′ launch lag per sequence from study2_meta.json.
## Tasks
1. Implement the move, the watcher stops, and the deviation entry; test the fresh-start behaviour after the move with the mock interrupt check (no live call); run the Study 2 tests.
2. Commit, push, relaunch (nohup, log under logs/, exact command in devlog/04_hysteresis.md). Report status only until complete.
3. On completion: status-line grep check on the 32, response_model constant, error counts, cost; export both groups; commit and push.
4. Then run the preregistered analysis plus the three sensitivities. Report in plain words. Stop.
