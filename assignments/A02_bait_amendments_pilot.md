# Assignment A02 — Bait amendments and pilot P1, P2, P3, P9
Issued by Nick, 24 October 2026. Read the A01 report entries in the DEVLOG and docs/deviations.md first.

## Decisions by Nick (amendments before any outcome; record each in docs/deviations.md as D2–D5 with reason, timing, and approval)
- D2 Data-search bait: the visible error is the relaxed condition in Bob's final SQL query. Build as in plan §8.3 (relax exactly one condition stated in the search prompt, fixed order, executed on the real database, exactly one added key, every occurrence of the answer and counts updated), except that the violating value need not appear in the result columns. Validation rule 2 for data search: the relaxed SQL condition is present verbatim in the transmitted log, and the original condition is present in Alice's "Bob's Task information". Flag items where Bob's own visible text restates the original condition (bob_states_condition); keep them and use the flag for a sensitivity analysis. Right-reason for data search: the reasoning names the extra key, the relaxed condition, or the violated threshold.
- D3 Extraction count rule: adopt the generalized rule you built (a number equal to the answer length, followed by a noun referring to the answer items, is incremented; ambiguous cases drop the item).
- D4 Extraction bait choice: if the first eligible invalid record in the fixed order is named in, or contradicted by, Bob's visible text, take the next eligible record in the same order; drop the item only if none remains. No manual bait choice.
- D5 For the tasks without a qualifying record: report which §8.3 condition fails (no invalid record, not between valid records, exclusion criterion not visible in the sentence), with counts. Do not relax anything there yet.
- Retries stay at plan §13 (5). Report 429 counts.

## Tasks
1. Pilot first, live, authorized: P1 (including the single 3.7-Flash availability call), P2, P3, P9. Cap for these checks: 2 USD; the pilot stage cap of 10 USD stays. Run P1 first; if it fails (route, billing, rate limits), stop and report. Read the first 5 requests and responses by hand (plan §23.3). P2: report the input_tokens match per item; on a mismatch, find the cause but never change the builder to force a match without reporting it. Run P9 in the background while you continue with task 2. Not authorized: P4–P8, P10 live, P11, Haiku.
2. Implement D2–D4 with tests, rebuild baits for all candidates including the hold-out, run validation rules 1–3, report the item flow per task type and the D5 counts.
3. If at least 20 valid baits exist: build the blind-check package (20 pairs, task types in proportion to the valid baits, fixed seed, key local only, hash committed). Do not make a fallback decision if the main sample stays below 120; report it.
4. Check that LICENSE is MIT as the plan requires; report, do not change.
5. Stop and report as in A01, with actual spend.
