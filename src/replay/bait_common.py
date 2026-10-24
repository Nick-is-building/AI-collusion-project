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
COUNT_MODES = ("plan_nouns", "any_noun")
ANY_NOUN_RE = re.compile(rf"\b(?P<num>{_NUM})\b(?P<mid>(?:[ \-][A-Za-z][\w\-]*){{0,2}}?)[ \-](?P<noun>[A-Za-z]{{3,}})\b", re.I)


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


def increment_counts(text: str, n: int, mode: str = "plan_nouns") -> tuple[str, list[dict]]:
    """Increment every count of the answer size n in `text`; raise Ambiguous for any other count."""
    changes = []
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


def stray_counts(text: str, n: int, mode: str = "plan_nouns") -> list[str]:
    """Occurrences of the answer size n (digits or number word) that the count rule does not cover,
    e.g. "12 lines", "8 students", or an enumeration "1. ... 8. ...". Such an item is ambiguous:
    the plan's rule would leave a visible count of n next to an answer of n + 1."""
    covered = [(m.start(), m.end()) for m in COUNT_RE.finditer(text)]
    if mode == "any_noun":
        covered += [(m.start(), m.end()) for m in ANY_NOUN_RE.finditer(text) if _value(m.group("num")) == n]
    pat = re.compile(rf"(?<![\w\-.]){n}(?![\w\-])|\b{NUM_WORDS[n]}\b" if n < len(NUM_WORDS) else rf"\b{n}\b", re.I)
    return [m.group(0) for m in pat.finditer(text) if not any(a <= m.start() < b for a, b in covered)]
