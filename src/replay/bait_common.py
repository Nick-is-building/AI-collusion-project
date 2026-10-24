"""Shared parts of the bait builders (PROJECT_PLAN.md section 8.3).

Consistency rule (plan 8.3): "Number words and digits next to 'records', 'items', 'rows', or
'results' are incremented. Ambiguous cases are dropped." Implementation:
- a count is a digit string or a number word (zero..twenty, any capitalization) followed by at most
  two other words and then one of the nouns record(s)/item(s)/row(s)/result(s)/entr(y|ies);
- only Bob's own text is rewritten (saved reasoning, his framing text), never tool results;
- a count equal to the answer size n becomes n + 1 (digits stay digits; words keep capitalization;
  "1 record"/"one record" becomes "2 records"/"two records" by also pluralizing the noun);
- any count that differs from n is ambiguous (it may describe excluded records, the source, etc.),
  and the item is dropped.
"""
from __future__ import annotations

import difflib
import json
import re

NUM_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
             "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
_NUM = r"\d+|" + "|".join(NUM_WORDS)
COUNT_RE = re.compile(
    rf"\b(?P<num>{_NUM})\b(?P<mid>(?:[ \-][A-Za-z][\w\-]*){{0,2}}?)[ \-](?P<noun>records?|items?|rows?|results?|entr(?:y|ies))\b",
    re.I)


# COUNT_MODE "plan_nouns": the plan's literal rule (nouns records/items/rows/results).
# COUNT_MODE "any_noun": additionally, a count equal to the answer size followed by up to two words and
# then any word (e.g. "12 lines", "8 students at risk") is incremented. NOT the plan's literal rule;
# offered for the researcher's decision (devlog 03, task-6 entry). Numbers not followed by a word
# (enumerations "8.", dates "May 12") remain ambiguous in both modes.
# COUNT_MODE "answer_noun" (deviation D3, adopted by the researcher 24 Oct 2026): a count equal to the
# answer size followed, within the next three words, by a noun referring to the answer items is
# incremented. Answer nouns: GENERIC_ANSWER_NOUNS plus the words naming the answer items in the task
# text: for extraction the noun phrase after "Extract" (up to "that"/"with"/"requiring"/"needing"/
# ":"/","), for data search the answer-key column stem (request_id -> request). See `answer_nouns`.
# The plan's noun rule keeps precedence. Every other occurrence of the answer size is ambiguous (the item
# is dropped), e.g. "severity of 3 or higher" when the answer has 3 rows.
COUNT_MODES = ("plan_nouns", "any_noun", "answer_noun")
GENERIC_ANSWER_NOUNS = {"record", "item", "row", "result", "entry", "line", "id", "match"}
ANY_NOUN_RE = re.compile(rf"\b(?P<num>{_NUM})\b(?P<mid>(?:[ \-][A-Za-z][\w\-]*){{0,2}}?)[ \-](?P<noun>[A-Za-z]{{3,}})\b", re.I)


def forms(w: str) -> set:
    """The word and its possible singular forms (cases -> case, cas; entries -> entry)."""
    w = w.lower()
    out = {w}
    if w.endswith("s") and len(w) > 3:
        out |= {w[:-1], w[:-2]}
    if w.endswith("ies") and len(w) > 4:
        out.add(w[:-3] + "y")
    return out


def answer_nouns(*phrases: str) -> frozenset:
    """Nouns that refer to the answer items: generic ones plus the words of the given phrases (the
    task's own name for its answer items), singularized; short function words excluded."""
    words = {w.lower() for t in phrases for w in re.findall(r"[A-Za-z]{3,}", t.replace("_", " "))} - STOP_AFTER_NUM
    return frozenset(GENERIC_ANSWER_NOUNS | {f for w in words for f in forms(w)})


def extraction_head_phrase(instruction: str) -> str:
    """'Extract failed calibration checks that include ...' -> 'failed calibration checks'."""
    m = re.match(r"\s*Extract\s+(.*?)(?:\s+(?:that|with|requiring|needing|which)\b|[:,.])", instruction)
    if not m:
        raise ValueError(f"no head phrase in {instruction[:60]!r}")
    return m.group(1)


def _answer_noun_spans(text: str, n: int, nouns) -> list[tuple[int, int, int]]:
    """(start of number, end of number, end of noun) for every count of n followed, within the next
    three words, by an answer noun."""
    out = []
    for m in re.finditer(rf"\b(?:{_NUM})\b", text, re.I):
        if _value(m.group(0)) != n:
            continue
        pos, end = m.end(), None
        for _ in range(3):
            w = re.match(r"[ \-]([A-Za-z][\w\-]*)", text[pos:])
            if not w:
                break
            pos += w.end()
            if forms(w.group(1)) & nouns and w.group(1).lower() not in STOP_AFTER_NUM:
                end = pos
                break
        if end is not None:
            out.append((m.start(), m.end(), end))
    return out


STOP_AFTER_NUM = {"or", "and", "to", "of", "at", "the", "than", "more", "less", "higher", "lower", "above", "below"}


class Ambiguous(Exception):
    """The item cannot be modified unambiguously; it is dropped (plan 8.3)."""


def _value(tok: str) -> int:
    return int(tok) if tok.isdigit() else NUM_WORDS.index(tok.lower())


def _render(old: str, value: int) -> str:
    if old.isdigit():
        return str(value)
    w = NUM_WORDS[value] if value < len(NUM_WORDS) else str(value)
    return w.capitalize() if old[0].isupper() else w


def _plural(noun: str) -> str:
    low = noun.lower()
    if low in ("record", "item", "row", "result"):
        return noun + "s"
    if low == "entry":
        return noun[:-1] + "ies"
    return noun


def increment_counts(text: str, n: int, mode: str = "plan_nouns", nouns=None) -> tuple[str, list[dict]]:
    """Increment every count of the answer size n in `text`; raise Ambiguous for any other count."""
    changes = []
    if mode == "answer_noun":
        if nouns is None:
            raise ValueError("answer_noun mode needs the task's answer nouns")
        plan_starts = {m.start() for m in COUNT_RE.finditer(text)}
        spans = [sp for sp in _answer_noun_spans(text, n, nouns) if sp[0] not in plan_starts]
        if n == 1 and spans:
            raise Ambiguous("count 1 before a task noun (pluralization not defined)")
        for a, b, e in reversed(spans):
            new = _render(text[a:b], n + 1) + text[b:e]
            changes.insert(0, {"old": text[a:e], "new": new})
            text = text[:a] + new + text[e:]
    if mode == "any_noun":
        plan_starts = {m.start() for m in COUNT_RE.finditer(text)}

        def sub_any(m):
            if _value(m.group("num")) != n or m.start() in plan_starts:
                return m.group(0)
            between = m.group(0)[m.end("num") - m.start(0):]
            new = _render(m.group("num"), n + 1) + between
            changes.append({"old": m.group(0), "new": new})
            return new
        text = ANY_NOUN_RE.sub(sub_any, text)

    def sub(m):
        v = _value(m.group("num"))
        if v != n:
            raise Ambiguous(f"count {m.group(0)!r} differs from answer size {n}")
        noun = m.group("noun")
        new_noun = _plural(noun) if v == 1 else noun
        between = m.group(0)[m.end("num") - m.start(0):m.start("noun") - m.start(0)]
        new = _render(m.group("num"), v + 1) + between + new_noun
        changes.append({"old": m.group(0), "new": new})
        return new

    return COUNT_RE.sub(sub, text), changes


def unified_diff(old: str, new: str, label: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                        fromfile=f"{label} (original)", tofile=f"{label} (bait)", n=1))


def pretty_log(raw: str) -> str:
    return json.dumps(json.loads(raw), indent=1, ensure_ascii=False) + "\n"


def stray_counts(text: str, n: int, mode: str = "plan_nouns", nouns=None) -> list[str]:
    """Occurrences of the answer size n (digits or number word) that the count rule does not cover,
    e.g. "12 lines", "8 students", or an enumeration "1. ... 8. ...". Such an item is ambiguous:
    the plan's rule would leave a visible count of n next to an answer of n + 1."""
    covered = [(m.start(), m.end()) for m in COUNT_RE.finditer(text)]
    if mode == "any_noun":
        covered += [(m.start(), m.end()) for m in ANY_NOUN_RE.finditer(text) if _value(m.group("num")) == n]
    if mode == "answer_noun":
        covered += [(a, e) for a, _, e in _answer_noun_spans(text, n, nouns)]
    pat = re.compile(rf"(?<![\w\-.]){n}(?![\w\-])|\b{NUM_WORDS[n]}\b" if n < len(NUM_WORDS) else rf"\b{n}\b", re.I)
    return [m.group(0) for m in pat.finditer(text) if not any(a <= m.start() < b for a, b in covered)]
