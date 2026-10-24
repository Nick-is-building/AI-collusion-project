# Assignment A06 — Decidability rubric, preregistered analyses, omission and distance addendum
Issued by Nick, 24 October 2026, after A04. Record D24–D26 in docs/deviations.md.

## Coordination
The A05 session builds Study 2 in this working tree at the same time. Stage explicit paths only (never git add -A or git add .), pull --rebase your own unpushed commits before pushing, append to shared files (docs/deviations.md, DEVLOG_INDEX.md) rather than rewriting them, and never touch src/hysteresis/, scripts/study2/, or Study 2 files.

## Decisions by Nick
- D24 Decidability rubric (D18): before any outcome is computed, write a rubric and classify all 35 natural-error items: is the error decidable from Bob's task instruction plus the transmitted log alone (yes/no/ambiguous), with a one-line reason; plus a deterministic lexical-overlap measure between the extra or missing record and the exclusion clause, computed for natural errors and for our baits. Classification is done by Claude Code reading, and is described as such. Commit before task 2.
- D25 Omission-bait addendum, fixed now, before the R1-live outcome is known: for record-extraction candidates in the main frame (not the hold-out), an omission version removes exactly one valid record from Bob's resolve_records arguments and result, the saved answer, every other occurrence of the answer, and counts (decremented with the D3 rule). Choice: valid records in a seed-2026 random order; skip a record named in Bob's visible text; drop the item if none remains. Validation: Shi et al.'s evaluator reports the removed record as missing; the removed record's sentence is present verbatim in the transmitted log (read_source result); diff saved. Variants: R1 and R4 on the omission version, two draws each; correct counterparts R0′ and R4-correct with two draws, reused from the main run where they exist and run where missing. Pre-specified test: Δ_om = Detection(R4) − Detection(R1) on omission versions, cluster sign-flip and cluster bootstrap as in plan §8.8, α = 0.05, outside the Holm family; D_om as in plan §8.6; descriptive comparison with commission detection and with natural omissions.
- D26 Distance control R5-post, fixed now: on the 40 R1-live items, bait version, R1 context with neutral Gutenberg filler inserted as one user message between Bob's round-1 message and the verdict prompt, token-matched (±2%) to the original rounds 2–5 of that episode; two draws. Comparison with R1 and R1-live, descriptive, with cluster bootstrap intervals. Purpose: separates distance from the evidence from conversation content.
- Stage cap for D25 and D26 together: 10 USD.
- Exploratory, labeled as such: equivalence reading of preregistered contrasts with margin ±0.10 (as for R5); right-reason detection by Claude Code reading next to the deterministic markers, with the P11 discrepancy (22 of 32 deterministic) disclosed.

## Tasks
1. D24 rubric and classification; commit and push.
2. Run the preregistered analyses: prereg-v1 (all primary, gatekeeping, secondary, cut-artifact, natural-error N1/N4 by error type and by decidability, sensitivities) and prereg-v1-r1live (including intermediate outcomes, reaction types, confirming readings). One verification script produces every number; commit outputs. Report the main figures to Nick right away, in plain words, before continuing.
3. Build D25 and D26, tests, then run them live within the cap; analyze as fixed above.
4. Stop and report: all figures from the verification script, clearly separated into confirmatory, addendum, and exploratory.
