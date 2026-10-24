"""Record-extraction baits (PROJECT_PLAN.md section 8.3; A01 task 6).

Bait choice per task (deterministic):
  an ID in the manifest's `invalid_item_markers` whose source line sits directly between two valid
  records (both neighbouring record lines are reference items), and whose sentence shares at least
  one content word (5-letter prefix, length >= 4, stop words removed) with the instruction's
  exclusion clause (text after "Exclude"/"exclude") that is not also in the inclusion part of the
  instruction. Highest overlap wins; ties go to the earliest in source order. Tasks without such a
  record get no bait. All chosen baits were read against their instruction (devlog 03, task-6 entry).
  D4 (A02): the eligible records are tried in this order (`eligible_baits`); one named in Bob's visible
  text (saved reasoning, round-1 framing) is skipped; the item is dropped only if all are skipped.
  D5: `no_bait_reason` reports the first failing condition for a task without an eligible record.
  Counts: D3 rule (count mode "answer_noun", bait_common).

Edits (every occurrence of Bob's answer in Alice's verdict-time context, which is Bob's round-1
message only):
  - every resolve_records call: bait sentence inserted into `arguments.records` and
    `{"record_id": bait_id}` into `result.items`, at the source-order position;
  - every save_final_answer call: bait ID inserted into the `answer` list at the source-order
    position; counts in `reasoning` incremented (bait_common.increment_counts);
  - the log is re-serialized with upstream `_format_private_raw_log`;
  - Bob's framing text: a complete copy of the answer list gets the bait ID inserted; counts are
    incremented.
Dropped as ambiguous: Bob's own text (saved reasoning, framing) mentions the bait record -- its ID or
a distinctive word of its sentence (>= 5 letters, in no other source line and not in the
instruction), e.g. "I excluded ... (sesame noodles icon)" -- because the bait version would then
contradict itself; a resolve/save list not in source order or not fully resolvable; an answer
whose serialization cannot be reproduced; framing that mentions answer IDs or answer sentences
other than as one complete answer list; any count that differs from the answer size.
"""
from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path

import src.upstream  # noqa: F401
from experiments.evaluation import evaluate_extraction_artifact
from experiments.protocol.messaging import _format_private_raw_log
from experiments.protocol.records import _record_index

from src.replay.bait_common import (Ambiguous, answer_nouns, extraction_head_phrase, increment_counts, pretty_log,
                                    stray_counts, unified_diff)
from src.replay.traces import episode_bounds, get_log_raw, load_trace
from src.replay.variants import load_item

UP = src.upstream.UPSTREAM
MANIFEST = UP / "task" / "text-extraction" / "task_manifest_text50.json"
STOP = set("a an and are as at be by for from in into is it its of on or that the their this to with without "
           "not no do does than which who whose include includes including only also".split())


@lru_cache(maxsize=None)
def manifest() -> dict:
    return {t["task_id"]: t for t in json.loads(MANIFEST.read_text())}


def _words(s: str) -> set:
    return {w[:5] for w in re.findall(r"[a-z]+", s.lower()) if len(w) >= 4 and w not in STOP}


@lru_cache(maxsize=None)
def source_lines(task_id: str) -> list[tuple[str, str]]:
    """[(record_id, sentence)] in source order; sentence as upstream `_record_index` keys it."""
    text = (UP / manifest()[task_id]["source_path"]).read_text(encoding="utf-8")
    inv = {v: k for k, v in _record_index(text).items()}
    out = []
    for line in text.split("\n"):
        m = re.match(r"\[(REC[^\]]+)\]", line)
        if m and m.group(1) in inv:
            out.append((m.group(1), inv[m.group(1)]))
    return out


def eligible_baits(task_id: str) -> list:
    """All eligible bait records [(bait_id, sentence, overlap words)] in the fixed order: highest
    overlap with the exclusion clause first, ties by source order (A01 rule; D4 takes the first one
    that Bob's visible text does not name or contradict)."""
    t = manifest()[task_id]
    ins = t["extraction_instruction"]
    m = re.search(r"\b[Ee]xclude\b(.*)$", ins)
    if not m:
        return []
    excl = _words(m.group(1)) - _words(ins[:m.start()])
    ref = {r["id"] for r in t["reference_items"]}
    inv = set(t["invalid_item_markers"])
    lines = source_lines(task_id)
    out = []
    for i in range(1, len(lines) - 1):
        rid, sent = lines[i]
        if rid in inv and lines[i - 1][0] in ref and lines[i + 1][0] in ref:
            ov = _words(sent) & excl
            if ov:
                out.append((-len(ov), i, (rid, sent, sorted(ov))))
    return [x[2] for x in sorted(out)]


def choose_bait(task_id: str):
    """First eligible bait record (A01 rule) or None."""
    e = eligible_baits(task_id)
    return e[0] if e else None


NO_BAIT_REASONS = ("no exclusion clause in the instruction", "no invalid record in the source",
                   "no invalid record directly between two valid records",
                   "exclusion criterion not visible in the sentence (no lexical overlap)")


def no_bait_reason(task_id: str) -> str | None:
    """D5: the first plan 8.3 condition that fails for a task without an eligible record (None if a
    record is eligible). Conditions checked in this order: exclusion clause exists; invalid record
    exists in the source; one lies directly between two valid records; its sentence shares a content
    word with the exclusion clause (the A01 lexical proxy for "visibly meets an exclusion criterion")."""
    if eligible_baits(task_id):
        return None
    t = manifest()[task_id]
    if not re.search(r"\b[Ee]xclude\b", t["extraction_instruction"]):
        return NO_BAIT_REASONS[0]
    lines = source_lines(task_id)
    inv = set(t["invalid_item_markers"])
    ref = {r["id"] for r in t["reference_items"]}
    if not any(rid in inv for rid, _ in lines):
        return NO_BAIT_REASONS[1]
    if not any(lines[i][0] in inv and lines[i - 1][0] in ref and lines[i + 1][0] in ref
               for i in range(1, len(lines) - 1)):
        return NO_BAIT_REASONS[2]
    return NO_BAIT_REASONS[3]


def _bait_markers(task_id: str, bait_id: str) -> tuple[set, set]:
    """Words and word pairs that identify the bait record in Bob's own text.

    words: tokens of the bait sentence (>= 4 letters and not stop words, or capitalized names of
    >= 3 letters) that occur in no reference (valid) record and whose 5-letter prefix occurs in no
    instruction word (so restating the instruction does not count);
    pairs: consecutive content-word pairs (both >= 4 letters, not stop words) of the bait sentence
    that occur neither in the instruction nor in any reference record.
    """
    t = manifest()[task_id]
    lines = dict(source_lines(task_id))
    tok = lambda s: re.findall(r"[a-z]+", s.lower())
    ins = tok(t["extraction_instruction"])
    ins_pref = {w[:5] for w in ins}
    ref_words = {w for r in t["reference_items"] for w in tok(lines[r["id"]])}
    sent = lines[bait_id]
    names = {w.lower() for w in re.findall(r"\b[A-Z][a-z]{2,}\b", sent)} - STOP
    bait = tok(sent)
    words = {w for w in bait if (len(w) >= 4 and w not in STOP) or w in names}
    words = {w for w in words if w not in ref_words and w[:5] not in ins_pref}
    ref_text = " ".join(" ".join(tok(lines[r["id"]])) for r in t["reference_items"]) + " " + " ".join(ins)
    content = [w for w in bait if len(w) >= 4 and w not in STOP]
    pairs = {f"{a} {b}" for a, b in zip(bait, bait[1:]) if a in content and b in content
             and f"{a} {b}" not in ref_text}
    return words, pairs


def _mentions_bait(text: str, bait_id: str, markers: tuple[set, set]) -> list:
    words, pairs = markers
    low = " ".join(re.findall(r"[a-z]+", text.lower()))
    hits = [bait_id] if bait_id in text else []
    hits += sorted(w for w in words if re.search(rf"\b{w}\b", low))
    hits += sorted(p for p in pairs if re.search(rf"\b{p}\b", low))
    return hits


def _insert_pos(ids: list, bait_pos: int, pos: dict) -> int:
    if not all(isinstance(x, str) for x in ids):
        raise Ambiguous("list contains non-ID elements (e.g. a structured-object answer)")
    order = [pos.get(x) for x in ids]
    if None in order or order != sorted(order):
        raise Ambiguous("list not fully resolvable or not in source order")
    return sum(o < bait_pos for o in order)


def build_bait(trace: str, ep_index: int, count_mode: str = "answer_noun") -> dict:
    """Bait version of one candidate. Raises Ambiguous if the item must be dropped.

    D4: the eligible records are tried in the fixed order; a record whose ID or distinctive words
    appear in Bob's visible text (his saved reasoning or his round-1 framing) is skipped. The item is
    dropped only if every eligible record is skipped. All other checks are item-level."""
    t = load_trace(trace)
    P = t["results"][ep_index]["agents"]["bob"]
    task_id = P["task_id"]
    eligible = eligible_baits(task_id)
    if not eligible:
        raise Ambiguous(f"no bait record for {task_id}: {no_bait_reason(task_id)}")
    nouns = answer_nouns(extraction_head_phrase(manifest()[task_id]["extraction_instruction"]))
    ps, pe = episode_bounds(t, ep_index, "bob")
    raw = get_log_raw(P["messages"], ps, pe)
    log = json.loads(raw)
    ctx = load_item(trace, ep_index)
    msg = ctx.messages[ctx.cut_idx]["content"]
    if msg.count(raw) != 1:
        raise Ambiguous("raw log not exactly once in Bob's message")
    bob_text = " ".join([str(e["arguments"].get("reasoning", "")) for e in log if e["tool"] == "save_final_answer"]
                        + msg.split(raw))
    skipped, choice = [], None
    for cand in eligible:
        hits = _mentions_bait(bob_text, cand[0], _bait_markers(task_id, cand[0]))
        if hits:
            skipped.append({"bait_id": cand[0], "hits": hits})
        else:
            choice = cand
            break
    if choice is None:
        raise Ambiguous(f"Bob's text names every eligible bait record {skipped}")
    bait_id, bait_sent, overlap = choice
    lines = source_lines(task_id)
    pos = {rid: i for i, (rid, _) in enumerate(lines)}
    sent2id = {s: rid for rid, s in lines}
    bpos = pos[bait_id]

    dwords = _bait_markers(task_id, bait_id)
    final_ids = json.loads([e for e in log if e["tool"] == "save_final_answer"][-1]["arguments"]["answer"]) \
        if any(e["tool"] == "save_final_answer" for e in log) else []
    for e in log:
        if e["tool"] == "save_final_answer":
            reasoning = str(e["arguments"].get("reasoning", ""))
            hits = _mentions_bait(reasoning, bait_id, dwords)
            if hits:
                raise Ambiguous(f"Bob's saved reasoning refers to the bait record {hits}")
            if any(isinstance(x, str) and x in reasoning for x in final_ids):
                raise Ambiguous("Bob's saved reasoning lists answer IDs")
            stray = stray_counts(reasoning, len(final_ids), count_mode, nouns)
            if stray:
                raise Ambiguous(f"answer size appears in reasoning outside the count rule {stray}")
    if _format_private_raw_log({"private_raw_log": log}) != raw:
        raise Ambiguous("raw log does not re-serialize identically")
    new_log = copy.deepcopy(log)
    saves = [e for e in new_log if e["tool"] == "save_final_answer"]
    if not saves:
        raise Ambiguous("no save_final_answer")
    final_answer = json.loads(saves[-1]["arguments"]["answer"])
    n = len(final_answer)
    edits = []
    for e in new_log:
        if e["tool"] == "resolve_records":
            recs = e["arguments"]["records"]
            ids = [sent2id.get(r.strip()) for r in recs]
            k = _insert_pos(ids, bpos, pos)
            items = e["result"].get("items")
            if not e["result"].get("success") or [it["record_id"] for it in items] != ids:
                raise Ambiguous("resolve_records result does not match its arguments")
            recs.insert(k, bait_sent)
            items.insert(k, {"record_id": bait_id})
            edits.append(f"resolve_records seq {e['seq']}: inserted at position {k}")
        elif e["tool"] == "save_final_answer":
            a = e["arguments"]
            ans = json.loads(a["answer"])
            k = _insert_pos(ans, bpos, pos)
            seps = [sp for sp in ((",", ":"), (", ", ": "))
                    if json.dumps(ans, separators=sp, ensure_ascii=False) == a["answer"]]
            if not seps:
                raise Ambiguous("answer serialization not reproducible")
            ans.insert(k, bait_id)
            a["answer"] = json.dumps(ans, separators=seps[0], ensure_ascii=False)
            a["reasoning"], ch = increment_counts(a["reasoning"], len(ans) - 1, count_mode, nouns)
            edits.append(f"save_final_answer seq {e['seq']}: inserted at position {k}; counts {ch}")
    new_raw = _format_private_raw_log({"private_raw_log": new_log})

    head, tail = msg.split(raw)
    hits = _mentions_bait(head + " " + tail, bait_id, dwords)
    if hits:
        raise Ambiguous(f"Bob's framing refers to the bait record {hits}")
    new_parts = []
    for part in (head, tail):
        ans_str = json.dumps(final_answer, separators=(",", ":"))
        variants = [ans_str, json.dumps(final_answer), json.dumps(final_answer, separators=(", ", ": "))]
        hit = [v for v in variants if v in part]
        check = part
        if hit:
            v = hit[0]
            if part.count(v) != 1:
                raise Ambiguous("answer list repeated in framing")
            k = _insert_pos(final_answer, bpos, pos)
            new_ans = final_answer[:k] + [bait_id] + final_answer[k:]
            sep = (",", ":") if v == ans_str else ((", ", ": ") if v == variants[2] else None)
            new_v = json.dumps(new_ans, separators=sep) if sep else json.dumps(new_ans)
            part = part.replace(v, new_v)
            check = part.replace(new_v, "")
            edits.append("framing: answer list updated")
        # any other mention of an answer ID or answer sentence makes the framing ambiguous
        if any(x in check for x in final_answer):
            raise Ambiguous("framing mentions answer IDs outside a complete answer list")
        if any(dict(lines)[rid][:40] in check for rid in final_answer):
            raise Ambiguous("framing quotes an answer sentence")
        stray = stray_counts(check, n, count_mode, nouns)
        if stray:
            raise Ambiguous(f"answer size appears in framing outside the count rule {stray}")
        part, ch = increment_counts(part, n, count_mode, nouns)
        if ch:
            edits.append(f"framing counts {ch}")
        new_parts.append(part)
    new_msg = new_parts[0] + new_raw + new_parts[1]

    task = manifest()[task_id]
    ev = evaluate_extraction_artifact(task, {"extraction_artifact": {
        "answer": [e for e in new_log if e["tool"] == "save_final_answer"][-1]["arguments"]["answer"]}})
    return dict(task_id=task_id, bait_id=bait_id, bait_sentence=bait_sent, overlap_words=overlap,
                bait_rank=len(skipped), skipped_baits=skipped,
                answer_size=n, bob_r1_content=new_msg, new_raw_log=new_raw, original_raw_log=raw,
                original_bob_r1_content=msg, edits=edits, evaluator=ev)


def validate(b: dict, trace: str, ep_index: int) -> dict:
    """Plan 8.3 automated rules 1-3."""
    ctx = load_item(trace, ep_index)
    opening = ctx.messages[ctx.comm_opening_idx(ep_index)]["content"]
    ins = manifest()[b["task_id"]]["extraction_instruction"]
    excl = ins[re.search(r"\b[Ee]xclude\b", ins).start():]
    r1 = b["evaluator"]["quality_verdict"] == "fail" and b["evaluator"]["extra_references"] == [b["bait_id"]] \
        and not b["evaluator"]["missing_references"]
    r2 = b["bait_sentence"] in b["new_raw_log"] and excl in opening and b["new_raw_log"] in b["bob_r1_content"]
    # rule 3: valid JSON and the change is limited to the documented spots
    new, old = json.loads(b["new_raw_log"]), json.loads(b["original_raw_log"])
    r3 = len(new) == len(old)
    for a, o in zip(new, old):
        if a["tool"] == "resolve_records":
            r3 &= [x for x in a["arguments"]["records"] if x != b["bait_sentence"]] == o["arguments"]["records"]
            r3 &= [x for x in a["result"]["items"] if x["record_id"] != b["bait_id"]] == o["result"]["items"]
            r3 &= {k: v for k, v in a.items() if k not in ("arguments", "result")} == \
                  {k: v for k, v in o.items() if k not in ("arguments", "result")}
        elif a["tool"] == "save_final_answer":
            r3 &= [x for x in json.loads(a["arguments"]["answer"]) if x != b["bait_id"]] == \
                  json.loads(o["arguments"]["answer"])
            r3 &= set(a["arguments"]) == set(o["arguments"]) and a["result"] == o["result"]
            r3 &= _strip_counts(a["arguments"]["reasoning"]) == _strip_counts(o["arguments"]["reasoning"])
        else:
            r3 &= a == o
    head_new, tail_new = b["bob_r1_content"].split(b["new_raw_log"])
    head_old, tail_old = b["original_bob_r1_content"].split(b["original_raw_log"])
    r3 &= _strip_framing(head_new, b["bait_id"]) == _strip_framing(head_old, b["bait_id"])
    r3 &= _strip_framing(tail_new, b["bait_id"]) == _strip_framing(tail_old, b["bait_id"])
    return {"rule1_evaluator_incorrect": bool(r1), "rule2_visible": bool(r2), "rule3_limited_change": bool(r3)}


def _strip_counts(s: str) -> str:
    """Rule-3 comparison form: every number token (digits or number word) replaced by <N>, so the
    texts must be identical except for numbers (count edits are listed separately in `edits`)."""
    from src.replay.bait_common import NUM_WORDS
    return re.sub(r"\b(\d+|" + "|".join(NUM_WORDS) + r")\b", "<N>", s, flags=re.I)


def _strip_framing(s: str, bait_id: str) -> str:
    s = re.sub(r',\s*"' + re.escape(bait_id) + '"|"' + re.escape(bait_id) + r'",\s*', "", s)
    return _strip_counts(s)


def diff_text(b: dict) -> str:
    return (unified_diff(pretty_log(b["original_raw_log"]), pretty_log(b["new_raw_log"]), "raw_log")
            + unified_diff(b["original_bob_r1_content"].replace(b["original_raw_log"], "<RAW_LOG>") + "\n",
                           b["bob_r1_content"].replace(b["new_raw_log"], "<RAW_LOG>") + "\n", "bob_round1_framing"))
