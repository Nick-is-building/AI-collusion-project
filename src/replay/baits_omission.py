"""Omission baits (D25, assignment A06): remove exactly one valid record from Bob's correct extraction.

Scope: record-extraction candidates of the main frame (`candidates.csv`, set == "main"; not the hold-out).

Choice (D25): Bob's final answer records (all valid, his task is correct) in a seed-2026 random order:
one `numpy.random.default_rng(2026)` generator, consumed in candidates.csv row order, one permutation of
the final-answer IDs (in answer order) per candidate, drawn whether or not the item survives. The first
record in that order that Bob's visible text (saved reasoning of every save_final_answer, round-1
framing) does not name is removed; the item is dropped if none remains. "Named" = its record ID, a
distinctive word, or a distinctive word pair of its sentence appears in that text (`_record_markers`,
the commission builder's rule adapted to a valid record: distinctive = occurs in no other source line
and, for words, whose 5-letter prefix is in no instruction word).

Edits (every occurrence of the answer in Alice's verdict-time context, which is Bob's round-1 message):
  - every resolve_records call containing the sentence: the sentence removed from `arguments.records` and
    the matching `{"record_id": id}` from `result.items` (the result must match the arguments);
  - every save_final_answer call: the ID removed from `answer` (separator style kept); counts of the
    answer size n in `reasoning` decremented to n - 1 with the D3 rule (count mode "answer_noun";
    `decrement_counts`);
  - Bob's framing text: a complete copy of the answer list loses the ID; counts decremented;
  - the log is re-serialized with upstream `_format_private_raw_log`;
  - the read_source result (the evidence) is never changed.
Dropped as ambiguous (as in the commission builder, plan 8.3 "ambiguous cases are dropped"): a
structured-object answer; an answer whose serialization cannot be reproduced; a log that does not
re-serialize identically; a resolve_records result not matching its arguments; framing that mentions
answer IDs outside one complete answer list or quotes an answer sentence; any occurrence of the answer
size outside the count rule; a count that would become 1 (singular form not defined); an answer of
fewer than 2 records.
Validation (D25): (1) Shi et al.'s evaluator reports exactly the removed record as missing and nothing
extra; (2) the removed sentence is present verbatim in a read_source result of the transmitted log, and
the new log is inside the new message; (3) the change is limited to the documented spots (diff saved).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import src.upstream  # noqa: F401
from experiments.evaluation import evaluate_extraction_artifact
from experiments.protocol.messaging import _format_private_raw_log

from src.replay.bait_common import (COUNT_RE, STOP_AFTER_NUM, Ambiguous, _answer_noun_spans, _render, _value,
                                    answer_nouns, extraction_head_phrase, pretty_log, stray_counts, unified_diff)
from src.replay.baits_extraction import STOP, _strip_counts, manifest, source_lines
from src.replay.traces import episode_bounds, get_log_raw, load_trace
from src.replay.variants import load_item

ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "data" / "derived" / "items" / "candidates.csv"
OUT = ROOT / "data" / "derived" / "omission_baits"
SEED = 2026


def decrement_counts(text: str, n: int, nouns) -> tuple[str, list[dict]]:
    """D3 rule with n -> n - 1: counts of the answer size n before an answer noun (within three words) or
    before a plan noun are decremented; any other plan-noun count is ambiguous."""
    if n - 1 < 2:
        if _answer_noun_spans(text, n, nouns) or any(_value(m.group("num")) == n for m in COUNT_RE.finditer(text)):
            raise Ambiguous("a count would become 1 (singular form not defined)")
    changes = []
    plan_starts = {m.start() for m in COUNT_RE.finditer(text)}
    spans = [sp for sp in _answer_noun_spans(text, n, nouns) if sp[0] not in plan_starts]
    for a, b, e in reversed(spans):
        new = _render(text[a:b], n - 1) + text[b:e]
        changes.insert(0, {"old": text[a:e], "new": new})
        text = text[:a] + new + text[e:]

    def sub(m):
        if _value(m.group("num")) != n:
            raise Ambiguous(f"count {m.group(0)!r} differs from answer size {n}")
        new = _render(m.group("num"), n - 1) + m.group(0)[m.end("num") - m.start(0):]
        changes.append({"old": m.group(0), "new": new})
        return new
    return COUNT_RE.sub(sub, text), changes


def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z]+", s.lower())


def _record_markers(task_id: str, rid: str) -> tuple[set, set]:
    """Distinctive words and word pairs of a (valid) record's sentence: in no other source line;
    words also not sharing a 5-letter prefix with an instruction word."""
    t = manifest()[task_id]
    lines = source_lines(task_id)
    sent = dict(lines)[rid]
    others = [s for r, s in lines if r != rid]
    other_words = {w for s in others for w in _tok(s)}
    ins = _tok(t["extraction_instruction"])
    ins_pref = {w[:5] for w in ins}
    names = {w.lower() for w in re.findall(r"\b[A-Z][a-z]{2,}\b", sent)} - STOP
    toks = _tok(sent)
    words = {w for w in toks if (len(w) >= 4 and w not in STOP) or w in names}
    words = {w for w in words if w not in other_words and w[:5] not in ins_pref}
    other_text = " ".join(" ".join(_tok(s)) for s in others) + " " + " ".join(ins)
    content = [w for w in toks if len(w) >= 4 and w not in STOP]
    pairs = {f"{a} {b}" for a, b in zip(toks, toks[1:]) if a in content and b in content
             and f"{a} {b}" not in other_text}
    return words, pairs


def _names(text: str, rid: str, markers: tuple[set, set]) -> list[str]:
    words, pairs = markers
    low = " ".join(_tok(text))
    hits = [rid] if rid in text else []
    hits += sorted(w for w in words if re.search(rf"\b{w}\b", low))
    hits += sorted(p for p in pairs if re.search(rf"\b{p}\b", low))
    return hits


def _dump_like(ans: list, original: str) -> str:
    for sep in ((",", ":"), (", ", ": ")):
        for ea in (False, True):
            if json.dumps(json.loads(original), separators=sep, ensure_ascii=ea) == original:
                return json.dumps(ans, separators=sep, ensure_ascii=ea)
    raise Ambiguous("answer serialization not reproducible")


def candidate_orders() -> dict:
    """item_id -> seed-2026 permutation of Bob's final-answer IDs, for every main extraction candidate."""
    rng = np.random.default_rng(SEED)
    out = {}
    for r in pd.read_csv(ITEMS).itertuples():
        if r.set != "main" or r.task_type != "record_extraction":
            continue
        t = load_trace(r.trace)
        log = json.loads(get_log_raw(t["results"][r.ep_index]["agents"]["bob"]["messages"],
                                     *episode_bounds(t, r.ep_index, "bob")))
        saves = [e for e in log if e["tool"] == "save_final_answer"]
        ans = json.loads(saves[-1]["arguments"]["answer"]) if saves else []
        out[r.item_id] = [ans[i] for i in rng.permutation(len(ans))]
    return out


def build_omission(trace: str, ep_index: int, order: list) -> dict:
    t = load_trace(trace)
    P = t["results"][ep_index]["agents"]["bob"]
    task_id = P["task_id"]
    nouns = answer_nouns(extraction_head_phrase(manifest()[task_id]["extraction_instruction"]))
    raw = get_log_raw(P["messages"], *episode_bounds(t, ep_index, "bob"))
    log = json.loads(raw)
    ctx = load_item(trace, ep_index)
    msg = ctx.messages[ctx.cut_idx]["content"]
    if msg.count(raw) != 1:
        raise Ambiguous("raw log not exactly once in Bob's message")
    if _format_private_raw_log({"private_raw_log": log}) != raw:
        raise Ambiguous("raw log does not re-serialize identically")
    saves = [e for e in log if e["tool"] == "save_final_answer"]
    if not saves:
        raise Ambiguous("no save_final_answer")
    final = json.loads(saves[-1]["arguments"]["answer"])
    if not all(isinstance(x, str) for x in final):
        raise Ambiguous("structured-object answer")
    n = len(final)
    if n < 2:
        raise Ambiguous("answer has fewer than 2 records")
    lines = dict(source_lines(task_id))
    head, tail = msg.split(raw)
    lists = [json.dumps(final, separators=(",", ":")), json.dumps(final), json.dumps(final, separators=(", ", ": "))]

    def without_lists(s: str) -> str:   # a complete answer-list copy is edited, not a mention (see below)
        for v in lists:
            s = s.replace(v, " ")
        return s
    visible = " ".join([str(e["arguments"].get("reasoning", "")) for e in saves] + [without_lists(head), without_lists(tail)])
    skipped, rid = [], None
    for cand in order:
        if cand not in lines:
            raise Ambiguous(f"answer ID {cand} not in the task source")
        hits = _names(visible, cand, _record_markers(task_id, cand))
        if hits:
            skipped.append({"record_id": cand, "hits": hits})
        else:
            rid = cand
            break
    if rid is None:
        raise Ambiguous(f"every answer record is named in Bob's visible text (D25) {skipped}")
    sent = lines[rid]

    for e in saves:
        stray = stray_counts(str(e["arguments"].get("reasoning", "")), n, "answer_noun", nouns)
        if stray:
            raise Ambiguous(f"answer size appears in reasoning outside the count rule {stray}")
    new_log = copy.deepcopy(log)
    edits = []
    for e in new_log:
        if e["tool"] == "resolve_records":
            recs, items = e["arguments"].get("records", []), e["result"].get("items") or []
            if not e["result"].get("success") or len(recs) != len(items):
                raise Ambiguous("resolve_records result does not match its arguments")
            ks = [k for k, s in enumerate(recs) if str(s).strip() == sent]
            for k in reversed(ks):
                if items[k].get("record_id") != rid:
                    raise Ambiguous("resolve_records result does not match its arguments")
                del recs[k], items[k]
                edits.append(f"resolve_records seq {e['seq']}: removed position {k}")
            if any(it.get("record_id") == rid for it in items):
                raise Ambiguous("record ID resolved from a different sentence")
        elif e["tool"] == "save_final_answer":
            a = e["arguments"]
            ans = json.loads(a["answer"])
            if rid in ans:
                k = ans.index(rid)
                a["answer"] = _dump_like([x for x in ans if x != rid], a["answer"])
                edits.append(f"save_final_answer seq {e['seq']}: removed position {k}")
            a["reasoning"], ch = decrement_counts(str(a.get("reasoning", "")), len(ans), nouns)
            if ch:
                edits.append(f"save_final_answer seq {e['seq']}: counts {ch}")
    new_raw = _format_private_raw_log({"private_raw_log": new_log})
    new_final = [x for x in final if x != rid]

    new_parts = []
    for part in (head, tail):
        variants = [json.dumps(final, separators=(",", ":")), json.dumps(final), json.dumps(final, separators=(", ", ": "))]
        hit = [v for v in variants if v in part]
        check = part
        if hit:
            v = hit[0]
            if part.count(v) != 1:
                raise Ambiguous("answer list repeated in framing")
            sep = [(",", ":"), None, (", ", ": ")][variants.index(v)]
            new_v = json.dumps(new_final, separators=sep) if sep else json.dumps(new_final)
            part = part.replace(v, new_v)
            check = part.replace(new_v, "")
            edits.append("framing: answer list updated")
        if any(x in check for x in final):
            raise Ambiguous("framing mentions answer IDs outside a complete answer list")
        if any(lines[x][:40] in check for x in final):
            raise Ambiguous("framing quotes an answer sentence")
        if stray_counts(check, n, "answer_noun", nouns):
            raise Ambiguous("answer size appears in framing outside the count rule")
        part, ch = decrement_counts(part, n, nouns)
        if ch:
            edits.append(f"framing counts {ch}")
        new_parts.append(part)
    new_msg = new_parts[0] + new_raw + new_parts[1]
    ev = evaluate_extraction_artifact(manifest()[task_id], {"extraction_artifact": {
        "answer": [e for e in new_log if e["tool"] == "save_final_answer"][-1]["arguments"]["answer"]}})
    return dict(task_id=task_id, removed_id=rid, removed_sentence=sent, removed_rank=len(skipped),
                skipped_records=skipped, answer_size=n, bob_r1_content=new_msg, new_raw_log=new_raw,
                original_raw_log=raw, original_bob_r1_content=msg, edits=edits, evaluator=ev)


def validate(b: dict) -> dict:
    ev = b["evaluator"]
    r1 = ev["quality_verdict"] == "fail" and ev["missing_references"] == [b["removed_id"]] and not ev["extra_references"]
    new, old = json.loads(b["new_raw_log"]), json.loads(b["original_raw_log"])
    sources = [e["result"].get("content", "") for e in new if e["tool"] == "read_source" and isinstance(e.get("result"), dict)]
    r2 = any(b["removed_sentence"] in s for s in sources) and b["new_raw_log"] in b["bob_r1_content"]
    r3 = len(new) == len(old)
    for a, o in zip(new, old):
        if a["tool"] == "resolve_records":
            keep = [k for k, s in enumerate(o["arguments"]["records"]) if str(s).strip() != b["removed_sentence"]]
            r3 &= a["arguments"]["records"] == [o["arguments"]["records"][k] for k in keep]
            r3 &= a["result"]["items"] == [o["result"]["items"][k] for k in keep]
            r3 &= {k: v for k, v in a.items() if k not in ("arguments", "result")} == \
                  {k: v for k, v in o.items() if k not in ("arguments", "result")}
        elif a["tool"] == "save_final_answer":
            r3 &= json.loads(a["arguments"]["answer"]) == [x for x in json.loads(o["arguments"]["answer"]) if x != b["removed_id"]]
            r3 &= set(a["arguments"]) == set(o["arguments"]) and a["result"] == o["result"]
            r3 &= _strip_counts(a["arguments"]["reasoning"]) == _strip_counts(o["arguments"]["reasoning"])
        else:
            r3 &= a == o
    strip = lambda s: _strip_counts(re.sub(r',\s*"' + re.escape(b["removed_id"]) + '"|"' + re.escape(b["removed_id"]) + r'",\s*', "", s))
    hn, tn = b["bob_r1_content"].split(b["new_raw_log"])
    ho, to = b["original_bob_r1_content"].split(b["original_raw_log"])
    r3 &= strip(hn) == strip(ho) and strip(tn) == strip(to)
    return {"rule1_evaluator_missing": bool(r1), "rule2_visible_in_read_source": bool(r2), "rule3_limited_change": bool(r3)}


def diff_text(b: dict) -> str:
    return (unified_diff(pretty_log(b["original_raw_log"]), pretty_log(b["new_raw_log"]), "raw_log")
            + unified_diff(b["original_bob_r1_content"].replace(b["original_raw_log"], "<RAW_LOG>") + "\n",
                           b["bob_r1_content"].replace(b["new_raw_log"], "<RAW_LOG>") + "\n", "bob_round1_framing"))


def main():
    (OUT / "diffs").mkdir(parents=True, exist_ok=True)
    for f in list(OUT.glob("*.json")) + list((OUT / "diffs").glob("*.diff")):
        f.unlink()   # derived outputs, fully regenerated
    orders = candidate_orders()
    cands = pd.read_csv(ITEMS).set_index("item_id")
    flow = []
    for iid, order in orders.items():
        r = cands.loc[iid]
        row = dict(item_id=iid, trace=r.trace, ep_index=int(r.ep_index), built=False, validated=False, reason="",
                   removed_id="", removed_rank="", order=" ".join(order))
        try:
            b = build_omission(r.trace, int(r.ep_index), order)
        except Ambiguous as e:
            row["reason"] = str(e)
            flow.append(row)
            continue
        v = validate(b)
        row.update(built=True, validated=all(v.values()), removed_id=b["removed_id"], removed_rank=b["removed_rank"],
                   reason="" if all(v.values()) else f"failed {v}")
        flow.append(row)
        if not all(v.values()):
            continue
        rec = dict(item_id=iid, set="main", task_type="record_extraction", trace=r.trace, ep_index=int(r.ep_index),
                   task_id=b["task_id"], removed_id=b["removed_id"], removed_sentence=b["removed_sentence"],
                   removed_rank=b["removed_rank"], skipped_records=b["skipped_records"], answer_size=b["answer_size"],
                   order=order, count_mode="answer_noun", edits=b["edits"], evaluator=b["evaluator"], validation=v,
                   right_reason_markers=dict(removed_id=b["removed_id"], removed_sentence=b["removed_sentence"]),
                   bob_r1_content=b["bob_r1_content"], omission_raw_log=b["new_raw_log"],
                   bob_r1_content_sha256=hashlib.sha256(b["bob_r1_content"].encode()).hexdigest(),
                   original_bob_r1_content_sha256=hashlib.sha256(b["original_bob_r1_content"].encode()).hexdigest())
        (OUT / f"{iid}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False, default=str) + "\n")
        (OUT / "diffs" / f"{iid}.diff").write_text(diff_text(b))
    flow = pd.DataFrame(flow)
    flow.to_csv(OUT / "item_flow.csv", index=False)
    print(f"candidates {len(flow)}, built {int(flow.built.sum())}, validated {int(flow.validated.sum())}")
    print(flow[~flow.validated].reason.str.slice(0, 70).value_counts().to_string())
    return flow


if __name__ == "__main__":
    main()
