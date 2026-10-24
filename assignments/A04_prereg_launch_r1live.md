# Assignment A04 — prereg-v1, main launch, R1-live
Issued by Nick, 24 October 2026, after the A03 report. Record D13–D16 in docs/deviations.md (reason, timing, approval). P11 is pilot data on the hold-out; per plan §10 it changes only scheduling and writing focus. Do not change baits, variants, sample, or analysis because of it.

## Decisions
- D13 R6 wording and placement (technical fix after P5: the manipulation did not reach the first verdict, 0 of 10 first submissions itemized). Data-search item list: "the value of the answer key column for every row of Bob's final answer", plus the quoted conditions (D11). The rule is stated in the schema field description and, in addition, in one sentence appended to the verdict prompt in R6 only (replaces D12). Record that R6 now differs from R1 in the schema field and one prompt sentence.
- D14 Fidelity level 1 (plan §8.7): report the raw exact-match rate and, next to it, the rate after accounting for the documented storage difference (−5 tokens per unmatched resolve_records item), with the evidence. Neither is relabeled as a pass of the original rule.
- D15 rep018_e02: apply D4 consistently (take the next eligible record).
- D16 R1-live gets its own preregistration addendum: prereg-v1 now covers everything except the R1-live driver; the R1-live subset of 40 and the flag rules are frozen in prereg-v1; after P7, a tag prereg-v1-r1live freezes the driver and any flag-rule clarification, before the R1-live run. Building R1-live is moved ahead of Haiku, 3.7 Flash, and Study 2 (a scheduling change permitted by plan §10).

## Tasks
1. Implement D13; rerun the R6 part of P5 (5 items, both versions; cap 0.30 USD) and report first-submission compliance. Whatever the compliance, continue; report it.
2. Implement D14 and D15; rerun make_prereg_files; run all tests. Then tag prereg-v1 (authorized) and push commit and tag.
3. Main run, authorized: stage cap 40 USD in configs/caps.yaml; launcher script; 4 workers; inside tmux or nohup with logs. Launch in two stages: first 5 complete calls per variant, read them by hand (plan §23.3), then the full run if they look normal; otherwise stop and report. Variant order shuffled per item as planned. Monitor errors, missing verdicts, response_model, cost.
4. While the main run is running: build the R1-live driver (plan §8.4), run P7 live on 2 items (cap 1 USD), apply flags A and B, report. Then prepare tag prereg-v1-r1live but do not tag; do not launch R1-live.
5. Study 2 estimate only (no building, no calls): realistic build time for status line, branching, and partner control; wall time and cost for P8 and for 30 and 40 pairs at 4 workers.
6. Stop and report: tags, main-run status and spend, first-read observations, R6 compliance, P7 result, Study 2 estimate. Do not report main-run outcome statistics before the run is complete.
