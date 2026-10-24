# Natural-error decidability rubric and classification (D24, assignment A06 task 1)

**Status:** written and committed before any outcome of the main run, R1-live, N1, or N4 was computed or looked at (D18). The classification was done by **Claude Code (Opus 5.5) reading the material**. It is one reader's judgement, not a validated human coding, and is described as such wherever it is used.

## Question

For each of the 35 natural-error items (`data/derived/items/natural_error_set.csv`): **is Bob's error decidable from Bob's task instruction plus the transmitted log alone?**
- *Task instruction*: the "Bob's Task information" section of Alice's communication opening, the only task description Alice sees.
- *Transmitted log*: Bob's raw log as it appears in his round-1 message: tool calls, results, his saved answer, and his saved reasoning.

## Material read per item

- The two inputs above, dumped by `scripts/a06/dump_natural_errors.py` into `scratch/a06/natural/` (local, reproducible).
- Shi et al.'s evaluator result, used only to identify **which** records, rows, or verdict are wrong. Alice never sees it. For extraction, the task's source file with valid and invalid markers, for the same purpose.
- No model output of any run.

## Categories

- **yes:** a careful reader with only the two inputs can establish that Bob's answer is wrong, because the transmitted material shows at least one of the following.
  - Extraction, commission: the extra record visibly fails a stated inclusion requirement, meets a stated exclusion clause, or is not an ID that the logged `resolve_records` returned (the answer definition).
  - Extraction, omission: the missing record appears verbatim in the logged `read_source` result, meets every stated requirement, and meets no exclusion clause, with no reading needed beyond the plain text.
  - Data search: the SQL in the log visibly deviates from a condition of the search prompt, including a literal that contradicts a value domain shown in the log.
  - Code analysis: Bob's verdict contradicts the code or specification shown in the log.
- **no:** the material needed to see the error is not in the two inputs, or the stated criteria support Bob's answer.
  - A required element is plainly absent from a missing record, so omitting it agrees with the stated instruction.
  - An extra record meets every stated criterion, so its invalid status depends on information Alice does not have.
  - The specification is not in the log.
- **ambiguous:** the evidence is in the log, but whether the record or answer meets the stated criteria depends on a reading that can reasonably go either way. Examples: "unanimously" as a vote count; a cure period as a notice period; a patch version given only by neighbouring lines.
- **Item level:** **yes** if at least one error component is yes, because one visible error suffices to reject. Otherwise **ambiguous** if at least one component is ambiguous. Otherwise **no**.

**Disclosure on the process.** The three categories and the item-level rule were fixed before reading. Two working rules were made explicit while reading the first extraction items and were then applied to all 35:
1. A required element that is plainly absent counts as **no**.
2. A required element that is present but debatable counts as **ambiguous**.

## Result (`data/derived/rubric/natural_error_decidability.csv`, one-line reason per item)

| error type | n | yes | ambiguous | no |
|---|---:|---:|---:|---:|
| extraction, omission | 19 | 2 | 12 | 5 |
| extraction, commission | 3 | 0 | 1 | 2 |
| extraction, both | 4 | 2 | 2 | 0 |
| data search | 6 | 6 | 0 | 0 |
| code analysis | 3 | 1 | 1 | 1 |
| **total** | **35** | **11** | **16** | **8** |

Observations from the reading:
- **Data search.** All 6 errors have the same cause. Bob wrote the status literal `'pending review'`, while the value domain in the logged `inspect_database` result lists `pending_review`. The query therefore silently drops those rows. This is visible, but only by comparing a literal against a schema listing.
- **Natural commissions.** None of the 3 pure commissions is a "yes":
  - two extra records (`REC29-72ed95`, `REC34-661410`) meet every stated criterion;
  - one is a near-duplicate with a vague deadline.

  Our baits, by contrast, were selected to meet an exclusion clause visibly (D7).
- **Omissions.** Most omissions concern a record whose required element (time window, cause, patch version, notice period) is missing or debatable in the sentence itself. Bob's saved reasoning often states exactly that ground, e.g. "excluded … missing a notice period".

## Lexical overlap with the exclusion clause (deterministic; `src/analysis/lexical_overlap.py`, `data/derived/rubric/lexical_overlap.csv`)

- **Rule:** the bait builder's word rule. Take the 5-letter prefixes of tokens with at least 4 letters, with stop words removed. The exclusion-clause words are those after "Exclude" that do not also occur before it. `overlap_n` is the number of shared words.
- **Scope:** extraction records only. Data-search and code items have no record sentence, and data-search prompts have no exclusion clause; those rows are kept and marked not applicable. One natural extra ID (`REC18-cdbdd8`, a mistyped ID) is not in any source and is marked not applicable.

| records | n | mean overlap_n | range |
|---|---:|---:|---|
| natural errors, missing records | 44 | 0.09 | 0–1 |
| natural errors, extra records | 6 | 0.00 | 0 |
| extraction baits (main 22 + hold-out 4) | 26 | 1.15 | 1–2 |

The baits were chosen by this overlap (≥ 1 by construction, D7), so the comparison describes how our baits differ from natural commissions. It is not an estimate from a random sample.
