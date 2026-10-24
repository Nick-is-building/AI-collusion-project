# Assignment A04 — addendum D17–D19 (verbatim)
Issued by Nick, 24 October 2026, after an independent review; received in the Claude Code session at about 10:45 UTC, with the instruction to continue A04 and record these as D17–D19 in docs/deviations.md.

- D17 Study 2 is not built (decision point, plan §11). Reason, technology and time only: the remaining build and run time is needed for R1-live, an omission-bait addendum, and the paper, and Study 2 would add three untested components. It goes into the appendix as a preregistered future study. Skip A04 task 5.
- D18 Analysis order: do not run the analysis scripts on main-run outcomes (including N1/N4) until a decidability rubric and classification for the natural-error set have been written and committed (next assignment). Operational monitoring (errors, missing verdicts, cost, response_model) is fine.
- D19 R1-live addendum (A04 task 4): run P7 on 4 items instead of 2 (cap 2 USD). The addendum prepared for tag prereg-v1-r1live must fix, before the R1-live run:
  1. The question, two-sided: do rounds 2–5 erode a detection that succeeds at the decision point (H5 open)?
  2. Comparison: d_i = y(R1-live) − mean of the two R1 draws of the same item. Alice's context up to the cut is byte-identical to the R1 bait request (hash check).
  3. Intermediate outcomes: (a) Alice names the bait in a live message (deterministic match on bait ID, bait sentence, or relaxed condition); (b) Bob's reaction type: concede, deny, or ignore, by a fixed keyword list plus a confirming reading; (c) final detection conditional on (a) and (b).
  4. Confound rule: because Bob's thought signatures encode his original selection, "conversation erodes detection" is claimed only if the effect persists in the subset without flags A and B.
  5. A pre-set fallback if the API rejects Bob's modified turns (whether Bob's signatures are then removed). Alice's context is never changed.
  6. Correct-version reference: the original trajectories of the 40 items with their natural verdicts, named as the false-rejection reference.
  7. Driver scope: rounds 2–5, the close of the communication phase, and the verdict phase of both agents; no feedback, no reflection.
  8. The flag B and reaction-type keyword lists are fixed after P7; confirming readings are done by Claude Code and described as such.
  9. Report the subset composition (task types, flagged items, trajectories, episodes) without changing it.

## Correction from Nick (verbatim), received in the Claude Code session at about 11:06 UTC, 24 October 2026

Correction from Nick: do not record D17. Study 2 will be built right after A04; it has priority over the omission-bait addendum because it has the longest run time. Do A04 task 5 as an implementation plan, not only an estimate: build steps and time for status line, branching and partner control; wall time and cost for P8 and for 40 and 50 pairs (all 50 of Shi et al.'s sequences) at 4, 8, 16 and 32 parallel workers, with all sequences and independent arms in parallel and only the required order inside a sequence (prefix, then branches; B before partner control); the Gemini rate limits that apply to this key, if they can be read without a paid call; the earliest realistic launch. No building and no calls yet. D18 and D19 stand.
