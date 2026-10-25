# A17 — Cross-family verifier: Claude Haiku 5.5 on the D25 contexts (timeboxed)
Authorization: Nick Wagner, 25 October 2026. Record as D41 in docs/deviations.md: exploratory cross-family transfer, the same design as D39 (A16) with Claude Haiku 5.5 as verifier; the preregistered Haiku arm (plan §8.5: R1 and R4 commission) was never run; this replaces it with the omission cells. Cells, tests, exclusions and rows fixed before any A17 call. Commit this file, D41, the caps line (stages.a17: 15.0) and the analysis script before any live call. Stage a17, cap 15 USD, Anthropic API only. Check that ANTHROPIC_API_KEY is set in .env (set or not set only; never print it); if not set, stop and report.

## Timebox rule
If the route does not pass the tests below on the first implementation, or the P6 check fails, stop, do not tune or retry, write the DEVLOG entry and report "built, not run". The Haiku arm then goes to Future Work.

## Route (plan §8.5)
- Model claude-haiku-5-5 via the Anthropic API (through LiteLLM if it converts cleanly; otherwise stop under the timebox rule). Price from the official Anthropic pricing page, recorded with URL and date in configs/prices.yaml.
- tool_choice auto; extended thinking on with high effort; Shi et al.'s retry logic when no tool call is returned (up to 3 verdict attempts).
- Gemini thought signatures cannot be sent to Anthropic and are removed; this is a documented, necessary difference for a cross-provider verifier (D41), not allowed for any Gemini route. Tool-call IDs with "/", "+", "=" are renamed consistently (names only). Consecutive same-role messages, if the API requires it, are merged without changing their text. The system prompt goes into Anthropic's system field. Document exactly what the converter does.
- Test on all items: after removing signatures and renaming IDs, every message text is identical to the Flash-Lite request for the same item, variant and version. Contexts above the Haiku context window: exclude, count, report; never truncate.
- Log response model and usage including thinking tokens per call; stop if the response model changes. Stop immediately on any billing or credit error; on 429 back off; stop if more than 10 rate-limit errors in 5 minutes do not clear.

## P6 (10 calls)
R1-om contexts of 10 D25 items not in the first stage-1 block: submit_verdict returned in at least 9 of 10 calls, with thinking present. If not, stop under the timebox rule.

## Items and exclusions
The 50 D25 omission items and their correct versions, with exactly the contexts used for Flash-Lite. Primary exclusion set: rep041_e06 and rep044_e03 (genuine residues found by D40). Sensitivities: all 50 items, and without all 4 D40-flagged items. Run all cells on all 50 items.

## Cells, analysis, rows
Identical to D39 (A16): omission R1-om, R4-om, R2-om, R1-om+CHK; correct R0′, R4, R2, R1+CHK; 2 draws each; no commission cell. Same seeded order (numpy default_rng(2026): items, then each item's cells), item blocks adjacent; stage 1 with 3 items, every call read by hand. Same primary family G, H, C (Holm over three), gatekeeping, secondaries and interpretation rows as D39. Paired verifier comparisons, descriptive: Haiku minus Flash-Lite, and Haiku minus 3.8 Flash if A16 has finished. Label everywhere: "Claude Haiku 5.5 judging in Gemini 3.1 Flash-Lite's trajectories (cross-family; Gemini thought signatures removed)". Call IDs a17:HAIKU:<item>:<variant>:<version>:<draw>. Stage-1 projection above 12 USD: drop draw 2 of every cell and record it in D41.

## Coordination and finish
Runs on the Anthropic API, so it may run while A16 runs on Gemini. Reuse A16's model wrapper once it is committed; do not modify A16's files (if you need something from it before it is committed, build your own small wrapper in src/replay/a17.py). Explicit git paths; pull --rebase. If P6 cannot start by 04:00 UTC on 26 October, stop and report "built, not run". After completion: verify_all (exit code checked), results_tables, full test suite, independent recount, readings as in A16; DEVLOG, index, commit, push; report as in A16.
Not authorized: any Gemini call, any other model or cell, any change to prereg tags, D25, D39 or earlier analyses.
