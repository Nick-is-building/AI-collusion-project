# A16 — Second verifier on identical contexts: Gemini 3.8 Flash on the D25 items
Authorization: Nick Wagner, 25 October 2026. Record as D39 in docs/deviations.md with this timing statement: exploratory transfer study, motivated by the Flash-Lite results of D25, A13, A14 and A15; cells, tests, exclusions and interpretation rows fixed before any A16 call. Commit this file (assignments/A16_second_verifier.md, verbatim), the D39 entry, the caps line (stages.a16: 40.0) and the analysis script before any live call. Stage a16, cap 40 USD. Nothing else is paid.

## 0. Model identity
Google deprecated gemini-3.7-flash and routes it to gemini-3.8-flash (https://ai.google.dev/gemini-api/docs/deprecations, read 25 Oct 2026). gemini-3.1-flash-lite is listed there without routing. A16 uses gemini/gemini-3.8-flash, called explicitly. Price: read https://ai.google.dev/gemini-api/docs/pricing and record it with URL and date in configs/prices.yaml (expected input 0.75 and output incl. thinking 3.75 USD per 1M tokens; if the page differs, use the page and report). Parameters exactly as the Flash-Lite main run (temperature 1.0, reasoning high, max output 64,000, tool_choice required, up to 3 verdict attempts), unchanged upstream request builder. Label everywhere: "Gemini 3.8 Flash judging in Gemini 3.1 Flash-Lite's trajectories" (newer model of the same family; history written by Flash-Lite). Never "in its own workflow".
Stop rules: any response_models entry other than gemini-3.8-flash stops the run; A10 guard (any 429 containing "spending cap"; more than 10 quota 429s in 5 minutes). Record in D39 that the served weights cannot be verified beyond Google's documentation.

## Coordination
Only one live Gemini run at a time on this machine. Another session runs a 0 USD residue scan and sensitivity analysis (D40) and later possibly a Claude Haiku run on the Anthropic API (D41) on the same contexts; coordinate by pull --rebase and explicit git paths. Build the model selection as a reusable wrapper (model argument) in a new module, so the Haiku session can reuse it. Do not edit prereg-hashed modules (src/replay/variants.py, r5.py, traces.py). If stage 1 cannot start by 04:00 UTC on 26 October, stop and report "built, not run".

## Items and contexts (0 USD)
The 50 D25 omission items and their correct versions, with exactly the contexts already built and used for Flash-Lite (R1-om, R4-om, R2-om, R1-om+CHK; R0′, R4, R2, R1+CHK on the correct version). Test that every A16 request's messages are byte-identical to the corresponding Flash-Lite request for the same item, variant and version, except the model string (hash test on all items).
Pre-specified exclusion: rep041_e06 is excluded from the A16 primary analysis because of the known residue (removed record visible in a failed tool call). Any further D25 item flagged by the D40 residue scan is also excluded from the primary analysis, provided the scan result is committed before the A16 analysis script reads any A16 outcome. Run all cells on all 50 items anyway; report the analysis on all 50 as a sensitivity.
Commission, descriptive: R1-com on the D25 items that also have a main-run commission bait (the 22 shared items), 1 draw.

## Stage 0 — route and history acceptance (about 0.5 USD, before any other call)
One R4 correct-version call (availability, price, response_models). Then R1-om, R2-om and R1-om+CHK on the first 3 items of the seeded order, one draw each: the API must accept the Flash-Lite thought signatures in the history without 400 errors. Any 400 on a signature or malformed history stops A16 (no signature stripping). Accepted calls count as draw 1 of their cells.

## Cells and order
Omission version, 2 draws: R1-om, R4-om, R2-om, R1-om+CHK. Correct version, 2 draws: R0′, R4, R2, R1+CHK. Commission: R1-com, 1 draw, shared items only. Seeded order (numpy default_rng(2026): items, then each item's cells), item blocks adjacent. Call IDs a16:XVER:<item>:<variant>:<version>:<draw>.
Stage 1: first 3 items, all cells; read every call by hand with a read_stage aid (context as claimed, parameters, response_models) before scaling. Project the full run from measured stage-1 cost per cell; if above 35 USD, drop in this order until it fits and record the drop in D39 before continuing: (a) R1-com; (b) draw 2 of R1+CHK (both versions); (c) draw 2 of every remaining cell.

## Analysis (fixed now; per-item draw means; trajectory clusters; cluster sign-flip 10,000 and cluster bootstrap 10,000, seed 2026, two-sided)
Primary family, Holm over exactly three, omission versions, primary item set:
- G = Detection(R4-om) − Detection(R1-om)
- H = Detection(R2-om) − Detection(R1-om)
- C = Detection(R1-om+CHK) − Detection(R1-om)
Gatekeeping per significant contrast (plan §8.6): D_i = [y(X, om) − y(X, correct)] − [y(R1, om) − y(R0′, correct)], with the R4, R2 and R1+CHK correct versions as counterparts; otherwise D descriptive.
Verifier comparison, descriptive with paired intervals (paired by item, cluster bootstrap): for every cell, 3.8 Flash minus Flash-Lite on the same items (Flash-Lite values from the existing a06/A13/A14 cells; no new Flash-Lite calls); same for G, H and C. No pooled test.
Secondary, descriptive: false rejection per cell and FR(X) − FR(R0′); equivalence flags (CI inside ±0.10); R1-com detection; named_accept and deterministic right-reason; draw agreement; missing-verdict sensitivities; the all-50-items sensitivity.
Interpretation rows (fixed now; "significant" = Holm p < 0.05):
1. G significant positive: the workflow gap for omissions replicates with a second, newer verifier on identical contexts.
2. G not significant and Detection(R1-om) ≥ 0.90: this verifier shows no measurable omission blindness on these contexts; the Flash-Lite gap is not general across verifiers. Report the interval and the equivalence flag.
3. G not significant and Detection(R1-om) < 0.90: inconclusive at this n, or omissions are hard in both contexts; report intervals, no claim.
4. H significant positive: the history effect replicates; otherwise report the interval.
5. C significant with FR(R1+CHK) − FR(R0′) ≤ 0.05 (point estimate): the check instruction transfers without false-rejection cost. C significant with a larger FR rise: criterion shift, report D. C not significant: no measurable transfer; report the interval.
6. Any pattern not covered: state which row is closest and which condition fails. Apply each row literally.

## Build, run, report
1. src/replay/a16.py (model argument, reuse of the existing context builders through wrappers), scripts/a16/{launch_a16,read_stage}.py, scripts/analysis/a16_addendum.py (verification.json key addendum.a16; results_tables.py new section), tests/test_a16.py (byte identity to the Flash-Lite requests except model, job list, adjacency, seed, exclusion rule, synthetic Holm-of-three with gatekeeping). Mock run complete before any live call.
2. Launch with nohup, logs/a16*.log, 4 workers; one background wait per launch; no polling.
3. After completion: verify_all (exit code checked, full log kept), results_tables, full test suite, independent recount from raw lines; read 5 ACCEPTs and 5 REJECTs per omission cell.
4. DEVLOG entries, DEVLOG_INDEX.md, commit, push. Report spend, served-model evidence, missing verdicts, G, H, C with Holm p, D and FR, the paired verifier comparison, which rows apply, in plain words, numbers only from the generated outputs.
Not authorized: any Flash-Lite call, any Haiku call, any other model or cell, any signature removal, any change to prereg tags, D25 or the A13–A15 analyses. Stop and ask if stage 0 returns a 400 on any history, if response_models differs, or if the projection exceeds 35 USD after drop (c).
