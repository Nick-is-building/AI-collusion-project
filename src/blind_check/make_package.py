"""Blind bait check package (PROJECT_PLAN.md section 8.3, rule 4; A01 task 7; A03 task 2).

D10 (A03): the blind human check is no longer a required step; the package is still generated so
another person may do it later; nothing waits for it.

Draws N random items with a validated bait, task types in proportion to the validated baits
(assignment A02: largest-remainder allocation of N over the task types; all validated baits, main
list and pilot hold-out). Seed SEED, numpy default_rng; draw order: per task type in sorted order
one sample without replacement from that type's items sorted by item_id; then one permutation of the
pair order; then one A/B coin per pair. Writes, per pair, one Markdown file with only
  - Bob's task information (the "### Bob's Task information" section of Alice's communication-phase
    prompt), and
  - the transmitted raw log of both versions (pretty-printed JSON, identical formatting),
labelled A and B. Bob's framing text is not shown. The form blind_check/ANSWERS.md asks, per pair,
which version contains the planted error and what the error is.

Layout for a tablet in the GitHub web view (A03): INSTRUCTIONS.md with one made-up worked example per
task type (not from any study item); each pair file starts with the task instruction (exclusion rules
on their own lines), then Version A and Version B as numbered steps (tool, arguments, result). The
results of `inspect_database` and `read_source` are always inside a collapsible <details> block,
decided by tool name only, never by length, so both versions are formatted identically.

The answer key goes to blind_check/key.local.json (git-ignored); only its SHA-256 is committed
(blind_check/key_sha256.txt). Refuses to run if fewer than N validated baits exist.

Usage: .venv/bin/python -m src.blind_check.make_package [--n 20] [--out blind_check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

from src.replay.variants import load_item

ROOT = Path(__file__).resolve().parents[2]
BAITS = ROOT / "data" / "derived" / "baits"
SEED = 2026

INSTRUCTIONS = """# Blind check — instructions

**Status:** optional (deviation D10). Nothing in the study waits for this check. Please do it only if
you can read English task descriptions and short SQL queries comfortably. Take your time.

## What you get

20 pairs. Each pair is one task that an AI agent ("Bob") did, and two versions of the log of his work,
**A** and **B**. The two versions are identical except that **exactly one of them contains one planted
error**. Your job, for each pair:

1. Read the task at the top of the pair file, especially the **exclusion rule** or every condition of
   the **search request**.
2. Compare version A and version B. Look at the final answer (`save_final_answer`) and at the step that
   produced it (`resolve_records` for record extraction, the SQL query for data search).
3. Write in [ANSWERS.md](ANSWERS.md) which version has the error and what the error is, in one
   sentence. "Not sure" is a valid answer; do not guess silently.

Use only the task text and the logs. Do not search for the answers elsewhere, and do not ask an AI
system: the point is whether a person can see the error from the log.

Long results (database schema, source text) are folded; tap "tap to open" to read them. Both versions
are folded the same way.

## Two worked examples (made up for these instructions; not from the study)

### Example 1 — record extraction

**Instruction:** Extract library book loans that include borrower, title, and due date.

**Exclusion rule:** Exclude loans that were already returned.

Version A, `save_final_answer`: `["REC-a1", "REC-b2", "REC-c3"]`

Version B, `save_final_answer`: `["REC-a1", "REC-b2", "REC-x9", "REC-c3"]`

In `resolve_records`, version B also lists the sentence *"Tom's copy of Dune was returned on Monday."*,
which resolved to `REC-x9`.

**Answer:** B. It adds REC-x9, a loan that was already returned, which the exclusion rule excludes.

### Example 2 — data search

**Search request:** Find open orders over 500 dollars placed in March 2025.

Version A, SQL: `... WHERE status = 'open' AND amount > 500 AND order_date BETWEEN '2025-03-01' AND '2025-03-31'`

Version B, SQL: `... WHERE status = 'open' AND amount >= 480 AND order_date BETWEEN '2025-03-01' AND '2025-03-31'`

Version B's result and final answer have one more row.

**Answer:** B. Its query lowers the amount threshold from "over 500" to 480, so it returns one order
that does not meet the request.

## What the error can look like

- **Record extraction:** one extra record ID in the answer. Its sentence (visible in `resolve_records`
  and in the source text) meets the exclusion rule.
- **Data search:** one condition of the SQL query is looser than the request says (a threshold, a list
  of allowed values, or a date range), so the result and the answer have one extra row.
"""


def task_information(trace: str, ep_index: int) -> str:
    ctx = load_item(trace, ep_index)
    opening = ctx.messages[ctx.comm_opening_idx(ep_index)]["content"]
    m = re.search(r"### Bob's Task information\n\n(.*?)\n\n### ", opening, re.S)
    return m.group(1).strip()


def pretty(raw: str) -> str:
    return json.dumps(json.loads(raw), indent=2, ensure_ascii=False)


COLLAPSED_RESULTS = ("inspect_database", "read_source")   # by tool name only (no length-dependent layout)


def _block(obj) -> str:
    return "```json\n" + json.dumps(obj, indent=2, ensure_ascii=False) + "\n```\n"


def render_log(raw: str, label: str) -> str:
    """One version's transmitted log as numbered steps. Layout depends only on the tool names."""
    out = [f"## Version {label}\n\n> Everything in this section is version {label}'s transmitted log.\n"]
    for step in json.loads(raw):
        rest = {k: v for k, v in step.items() if k not in ("seq", "tool", "arguments", "result")}
        out.append(f"\n### {label} · step {step.get('seq')}: `{step['tool']}`\n")
        if step.get("arguments"):
            args = step["arguments"]
            if step["tool"] == "query_database" and set(args) == {"sql"}:
                out.append("\nSQL query:\n\n```sql\n" + args["sql"].strip() + "\n```\n")
            else:
                out.append("\nArguments:\n\n" + _block(args))
        if rest:
            out.append("\nOther fields:\n\n" + _block(rest))
        if "result" in step:
            if step["tool"] in COLLAPSED_RESULTS:
                res = step["result"]
                if step["tool"] == "read_source" and isinstance(res.get("content"), str):
                    body = ("Source text (one record per line):\n\n```text\n" + res["content"].strip() + "\n```\n"
                            + ("" if set(res) == {"success", "content"} else "\n" + _block(
                                {k: v for k, v in res.items() if k != "content"})))
                else:
                    body = _block(res)
                out.append(f"\n<details><summary>Result of {step['tool']} (tap to open)</summary>\n\n"
                           + body + "\n</details>\n")
            else:
                out.append("\nResult:\n\n" + _block(step["result"]))
    return "".join(out)


def format_task_information(info: str) -> str:
    """Task information with the instruction first and each exclusion rule on its own line."""
    lines = []
    for line in info.splitlines():
        m = re.match(r"(Extraction instruction:\s*)(.*?)\s*(\b[Ee]xclude\b.*)?$", line)
        if m and m.group(3):
            lines.append(f"**Instruction:** {m.group(2)}\n\n**Exclusion rule:** {m.group(3)}")
        elif line.startswith("Extraction instruction:"):
            lines.append("**Instruction:** " + line.split(":", 1)[1].strip())
        elif line.startswith("Natural-language search prompt:"):
            lines.append("**Search request (every condition must hold):** " + line.split(":", 1)[1].strip())
        elif line.strip():
            k, _, v = line.partition(":")
            lines.append(f"**{k.strip()}:** {v.strip()}" if v else line)
    return "\n\n".join(lines)


def allocate(counts: dict, n: int) -> dict:
    """Largest-remainder allocation of n over the types (ties by type name)."""
    total = sum(counts.values())
    quota = {t: n * c / total for t, c in counts.items()}
    alloc = {t: int(q) for t, q in quota.items()}
    for t in sorted(quota, key=lambda t: (-(quota[t] - alloc[t]), t))[:n - sum(alloc.values())]:
        alloc[t] += 1
    return alloc


def make(n: int, out: Path, seed: int = SEED, baits_dir: Path = BAITS) -> dict:
    recs = [json.loads(p.read_text()) for p in sorted(baits_dir.glob("*.json"))]
    if len(recs) < n:
        raise SystemExit(f"blocked: {len(recs)} validated baits, {n} pairs required")
    rng = np.random.default_rng(seed)
    by_type: dict = {}
    for r in recs:
        by_type.setdefault(r["task_type"], []).append(r)
    alloc = allocate({t: len(v) for t, v in by_type.items()}, n)
    chosen = []
    for t in sorted(by_type):
        items = sorted(by_type[t], key=lambda r: r["item_id"])
        chosen += [items[i] for i in sorted(rng.choice(len(items), size=alloc[t], replace=False))]
    chosen = [chosen[i] for i in rng.permutation(len(chosen))]
    (out / "pairs").mkdir(parents=True, exist_ok=True)
    for f in (out / "pairs").glob("*.md"):
        f.unlink()   # the package is regenerated as a whole
    key = {"seed": seed, "n": n, "allocation": alloc, "pairs": {}}
    form = ["# Blind check — answer form\n\n",
            "See [INSTRUCTIONS.md](INSTRUCTIONS.md). For each pair: which version (A or B) contains the planted "
            "error, and what the error is (one sentence). \"Not sure\" is a valid answer.\n"]
    index = ["\n## Pairs\n\n"]
    for k, rec in enumerate(chosen, 1):
        from src.replay.traces import episode_bounds, get_log_raw, load_trace
        t = load_trace(rec["trace"])
        raw = get_log_raw(t["results"][rec["ep_index"]]["agents"]["bob"]["messages"],
                          *episode_bounds(t, rec["ep_index"], "bob"))
        bait_raw = rec["bait_raw_log"]
        assert bait_raw in rec["bob_r1_content"]
        json.loads(bait_raw)
        bait_is_a = bool(rng.integers(0, 2))
        a, b = (bait_raw, raw) if bait_is_a else (raw, bait_raw)
        pid = f"pair_{k:02d}"
        kind = "record extraction" if rec["task_type"] == "record_extraction" else "data search"
        (out / "pairs" / f"{pid}.md").write_text(
            f"# {pid} ({kind})\n\n[Instructions](../INSTRUCTIONS.md) · [Answer form](../ANSWERS.md)\n\n"
            f"## The task the agent had to do\n\n{format_task_information(task_information(rec['trace'], rec['ep_index']))}"
            f"\n\nExactly one of the two versions below contains one planted error. Compare them with the task."
            f"\n\n---\n\n{render_log(a, 'A')}\n\n---\n\n---\n\n{render_log(b, 'B')}\n\n---\n\n"
            f"End of {pid}. [Answer form](../ANSWERS.md)\n")
        key["pairs"][pid] = {"item_id": rec["item_id"], "task_type": rec["task_type"],
                             "bait_version": "A" if bait_is_a else "B", "bait_id": rec["bait_id"]}
        if rec["task_type"] == "record_extraction":
            key["pairs"][pid]["error"] = f"invalid record added: {rec['bait_sentence']}"
        else:
            key["pairs"][pid]["error"] = (f"query condition relaxed: {rec['original_condition']} -> "
                                          f"{rec['relaxed_condition']}; extra row {rec['added_key']}")
        form.append(f"\n## {pid}\n\n- Version with the error (A / B / not sure):\n- The error:\n")
        index.append(f"- [{pid}](pairs/{pid}.md) ({kind})\n")
    (out / "ANSWERS.md").write_text("".join(form))
    (out / "INSTRUCTIONS.md").write_text(INSTRUCTIONS + "".join(index))
    old_form = out / "answers_nick.md"
    if old_form.exists():
        old_form.unlink()
    key_bytes = json.dumps(key, indent=1, ensure_ascii=False).encode()
    (out / "key.local.json").write_bytes(key_bytes)
    digest = hashlib.sha256(key_bytes).hexdigest()
    (out / "key_sha256.txt").write_text(f"{digest}  key.local.json\n")
    return {"n": n, "allocation": alloc, "key_sha256": digest}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "blind_check"))
    a = ap.parse_args()
    print(make(a.n, Path(a.out)))


if __name__ == "__main__":
    sys.exit(main())
