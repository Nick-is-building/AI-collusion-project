# Assignment A08 — Exhaustive source classification (R6x), R6 false rejections on omissions, results tables
Issued by Nick, 24 October 2026, after A07.

## Decision by Nick (fixed now, before its own run; motivated by the R6s mechanism, which is reported unchanged)
R6x: on the 50 validated omission items, omission and correct versions, R1 context (cut), two draws each. The verdict tool gains a field source_classification: every sentence of the read_source result in Bob's transmitted log, verbatim, each labeled include or exclude according to the extraction instruction. The rule is stated in the schema and in one sentence appended to the verdict prompt (as D13). Deterministic gate: every source sentence appears exactly once and verbatim; otherwise one retry with a generic message that never names a sentence; a non-compliant ACCEPT after the retry becomes a gate REJECT; a non-compliant REJECT stays a REJECT. Primary outcome: the first verdict. Pre-specified test: Detection(R6x) − Detection(R1) on omission versions, cluster sign-flip and cluster bootstrap (plan §8.8), α = 0.05, outside the Holm family. Secondary, pre-specified: final gated verdict, false rejections against R0′ with intervals, compliance rate of the first submission, and detection conditional on the missing sentence being labeled include. Stage cap 6 USD. Read the first 5 calls per cell before scaling.

## Tasks
1. Build and run R6x as fixed. Report the result in plain words right away.
2. Run the existing R6 on the correct versions of the 50 omission items, two draws (within the same cap), and replace the borrowed false-rejection rate in figure 4.
3. Extend verify_all.py and update figure 4 (R6, R6s, R6x operating points).
4. Write paper/results_tables.md: every number the paper will need for Study 1 and the addenda, in plain tables, each with its key in verification.json, grouped as confirmatory, addendum, exploratory. No interpretation.
5. Stop and report.
