"""Data-search baits (PROJECT_PLAN.md section 8.3 as amended by deviations D2 and D6; A02, A03).

The visible error is one relaxed condition in Bob's final SQL query (D2). The violating value need
not appear in the result columns (D2 drops that part of plan 8.3; Bob's queries return only the key).

Answer query: the last successful `query_database` call in Bob's raw log whose result rows equal the
saved answer (all 101 data-search candidates have one; checked in `answer_query`).

Eligible conditions ("stated in the search prompt", order: see D6 below; parsed from Bob.s WHERE
clause; top-level AND conjuncts only):
  cmp      `col >= | > | <= | < | = literal`
  between  `col BETWEEN a AND b`
  in       `col IN (v1, ..., vk)`
  A conjunct is eligible if its column name appears in the task's `reference_sql` and its literal(s)
  appear in the search prompt (`literal_in_prompt`: numbers as numbers, "$20000+" and "20,000"
  included; dates verbatim; text values with "_" read as " ", whole words, case-insensitive).
  Not eligible: OR groups, column-to-column comparisons, LIKE, NOT IN, IS NULL.

Conjunct order (deviation D6, assignment A03; replaces A02's "order of appearance"): eligible
conjuncts are tried by class, then in the order of appearance in Bob's WHERE clause within a class:
  1 categorical  `in` lists and `=` with a non-date literal (status, tier, category, ...)
  2 numeric      `cmp` (>=, >, <=, <) or `between` with numeric literals
  3 text         `cmp`/`between` with non-date text literals (LIKE and EXISTS are not eligible under
                 the D2 parser, so this class holds only text inequalities; none occur in the sample)
  4 date         `cmp`/`between` with YYYY-MM-DD literals (the date range last)
`condition_class` records the class of the chosen conjunct.

Relaxations of one eligible conjunct, in this fixed order:
  cmp >=, >   lower the bound to the nearest excluded value (largest value below the bound among rows
              meeting all other conditions), written as `col >= v'` (">" becomes ">=").
  cmp <=, <   symmetric: `col <= v'` with the smallest excluded value above the bound.
  cmp =       treated as a one-value IN list: `col IN (v, w)`.
  between     upper bound first (nearest excluded value above b), then lower bound (below a).
  in          one value appended, candidates in ascending order of their text: `col IN (..., w)`.
The first relaxation (conjunct order, then candidate order) whose query, executed on the real
database, returns exactly the original rows (same relative order) plus one row is the bait. Items
without one are dropped.

Edits (every occurrence of Bob's answer in Alice's verdict-time context = Bob's round-1 message):
  - the answer query: `arguments.sql` with the conjunct replaced; `result` = the relaxed query's
    output computed exactly as upstream `_query_database` does (default max_rows 100);
  - every save_final_answer whose answer equals the final answer: the new row inserted at its
    position in the query result (serialization style kept); counts in `reasoning` incremented
    (count rule D3, answer nouns = answer-key stem);
  - Bob's framing: a complete copy of the answer list updated; counts incremented.
Dropped as ambiguous: the added key appears in Bob's own text (reasoning or framing); Bob's text
lists answer keys other than as one complete answer list; any other count of the answer size; the
original query result cannot be reproduced on the database; truncated results.

Flag (kept, D2): `bob_states_condition` -- Bob's own visible text restates the original condition:
its saved reasoning or framing contains the original conjunct verbatim (whitespace-normalized,
case-insensitive) or the violated literal(s) (cmp/between: the bound; in: every listed value), or
another of his queries in the log contains the original conjunct verbatim. `bob_states_condition_where`
lists the sources.
"""
from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path

import src.upstream  # noqa: F401
from experiments.evaluation import evaluate_data_search_artifact
from experiments.protocol.databases import _connect_readonly_sqlite, _sqlite_rows
from experiments.protocol.messaging import _format_private_raw_log

from src.replay.bait_common import Ambiguous, answer_nouns, increment_counts, stray_counts
from src.replay.traces import episode_bounds, get_log_raw, load_trace
from src.replay.variants import load_item

UP = src.upstream.UPSTREAM
MANIFEST = UP / "task" / "data-search" / "task_manifest_data_search50.json"
DEFAULT_MAX_ROWS = 100   # upstream _query_database default
SEPARATORS = ((",", ":"), (", ", ": "), (", ", ":"), (",", ": "))   # answer serialization styles seen in Bob's saves


@lru_cache(maxsize=None)
def manifest() -> dict:
    return {t["task_id"]: t for t in json.loads(MANIFEST.read_text())}


def db_path(task: dict) -> Path:
    return (UP / task["database_path"]).resolve()


def run_query(task: dict, sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> dict:
    """The `result` upstream `_query_database` would log for `sql` (success path only)."""
    row_limit = max(1, min(int(max_rows or 100), 500))
    with _connect_readonly_sqlite(db_path(task)) as conn:
        cur = conn.execute(sql.strip())
        fetched = cur.fetchmany(row_limit + 1)
        cols = [c[0] for c in cur.description or []]
        rows = _sqlite_rows(cur, fetched[:row_limit])
    return {"success": True, "columns": cols, "truncated": len(fetched) > row_limit, "rows": rows}


def _query_all(task: dict, sql: str) -> list[tuple]:
    with _connect_readonly_sqlite(db_path(task)) as conn:
        return [tuple(r) for r in conn.execute(sql.strip()).fetchall()]


# ---------------------------------------------------------------- SQL text helpers

def _scan(s: str):
    """Yield (index, char, depth) for characters outside quotes."""
    depth, q, i = 0, None, 0
    while i < len(s):
        ch = s[i]
        if q:
            if ch == q:
                if i + 1 < len(s) and s[i + 1] == q:
                    i += 2
                    continue
                q = None
            i += 1
            continue
        if ch in "'\"":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        else:
            yield i, ch, depth
        i += 1


def _kw_at(s: str, i: int, kw: str) -> bool:
    return (re.match(kw + r"\b", s[i:], re.I) is not None
            and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] in "_.")))


def where_span(sql: str) -> tuple[int, int]:
    """(start, end) of the top-level WHERE body."""
    start = end = None
    for i, ch, d in _scan(sql):
        if d != 0:
            continue
        if start is None and _kw_at(sql, i, "WHERE"):
            start = i + 5
        elif start is not None and any(_kw_at(sql, i, k) for k in ("GROUP", "ORDER", "LIMIT", "HAVING")):
            end = i
            break
        elif start is not None and ch == ";":
            end = i
            break
    if start is None:
        raise Ambiguous("answer query has no WHERE clause")
    return start, len(sql) if end is None else end


def select_span(sql: str) -> tuple[int, int]:
    """(start, end) of the top-level select list (after SELECT [DISTINCT], before FROM)."""
    s = None
    for i, ch, d in _scan(sql):
        if d != 0:
            continue
        if s is None and _kw_at(sql, i, "SELECT"):
            s = i + 6
            m = re.match(r"\s+DISTINCT\b", sql[s:], re.I)
            if m:
                s += m.end()
        elif s is not None and _kw_at(sql, i, "FROM"):
            return s, i
    raise Ambiguous("no top-level SELECT ... FROM")


def conjuncts(where: str) -> list[str]:
    """Top-level AND conjuncts of a WHERE body (BETWEEN x AND y kept together), stripped."""
    parts, start, between = [], 0, False
    for i, ch, d in _scan(where):
        if d != 0:
            continue
        if _kw_at(where, i, "BETWEEN"):
            between = True
        elif _kw_at(where, i, "AND"):
            if between:
                between = False
            else:
                parts.append(where[start:i])
                start = i + 3
    parts.append(where[start:])
    return [p.strip() for p in parts if p.strip()]


_LIT = r"'(?:[^']|'')*'|-?\d+(?:\.\d+)?"
_COL = r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?"


def parse(conj: str) -> dict | None:
    m = re.fullmatch(rf"({_COL})\s+BETWEEN\s+({_LIT})\s+AND\s+({_LIT})", conj, re.I | re.S)
    if m:
        return dict(kind="between", col=m.group(1), lits=[m.group(2), m.group(3)])
    m = re.fullmatch(rf"({_COL})\s+IN\s*\(\s*((?:{_LIT})(?:\s*,\s*(?:{_LIT}))*)\s*\)", conj, re.I | re.S)
    if m:
        return dict(kind="in", col=m.group(1), lits=re.findall(_LIT, m.group(2)))
    m = re.fullmatch(rf"({_COL})\s*(>=|<=|>|<|=)\s*({_LIT})", conj, re.S)
    if m:
        return dict(kind="cmp", col=m.group(1), op=m.group(2), lits=[m.group(3)])
    return None


def lit_value(lit: str):
    if lit.startswith("'"):
        return lit[1:-1].replace("''", "'")
    return float(lit) if "." in lit else int(lit)


def render(value, like: str) -> str:
    """SQL literal for `value`, in the style of the original literal `like`."""
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, float) and value.is_integer() and "." not in like:
        return str(int(value))
    return repr(value) if isinstance(value, float) else str(value)


def _prompt_numbers(prompt: str) -> set:
    return {float(x.replace(",", "")) for x in re.findall(r"(?<![\w.\-])\d[\d,]*(?:\.\d+)?(?![\d\-])", prompt)}


def literal_in_prompt(lit: str, prompt: str) -> bool:
    v = lit_value(lit)
    if isinstance(v, (int, float)):
        return float(v) in _prompt_numbers(prompt)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return v in prompt
    words = v.replace("_", " ").lower()
    return re.search(rf"(?<![\w]){re.escape(words)}(?![\w])", prompt.lower()) is not None


def column_in_reference(col: str, task: dict) -> bool:
    name = col.split(".")[-1].lower()
    where = task["reference_sql"].lower().split("where", 1)[-1]
    return re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", where) is not None


def eligible(conj: str, task: dict) -> dict | None:
    p = parse(conj)
    if p is None or not column_in_reference(p["col"], task):
        return None
    if not all(literal_in_prompt(x, task["search_prompt"]) for x in p["lits"]):
        return None
    return p


# ---------------------------------------------------------------- relaxation search

def _probe(task, sql, conj, others_where_sql) -> list:
    """Distinct values of the conjunct's column among rows that meet all other conditions but not
    this one."""
    s0, s1 = select_span(sql)
    w0, w1 = where_span(sql)
    p = parse(conj)
    where = (others_where_sql + " AND " if others_where_sql else "") + f"NOT ({conj})"
    probe = sql[:s0] + " " + p["col"] + " AS __bait_v " + sql[s1:w0] + " " + where + " " + sql[w1:].rstrip().rstrip(";")
    vals = {r[0] for r in _query_all(task, probe) if r[0] is not None}
    return list(vals)


def relaxations(task: dict, sql: str, conj: str, p: dict, others: str):
    """Yield (relaxed conjunct text, violated literal, added value) in the fixed order."""
    vals = _probe(task, sql, conj, others)
    kind = p["kind"]
    if kind == "cmp" and p["op"] in (">=", ">"):
        b = lit_value(p["lits"][0])
        for v in sorted((x for x in vals if _lt(x, b) or (p["op"] == ">" and x == b)), reverse=True):
            yield f"{p['col']} >= {render(v, p['lits'][0])}", p["lits"][0], v
    elif kind == "cmp" and p["op"] in ("<=", "<"):
        b = lit_value(p["lits"][0])
        for v in sorted(x for x in vals if _lt(b, x) or (p["op"] == "<" and x == b)):
            yield f"{p['col']} <= {render(v, p['lits'][0])}", p["lits"][0], v
    elif kind == "cmp" and p["op"] == "=":
        for v in sorted(vals, key=str):
            yield f"{p['col']} IN ({p['lits'][0]}, {render(v, p['lits'][0])})", p["lits"][0], v
    elif kind == "between":
        a, b = (lit_value(x) for x in p["lits"])
        for v in sorted(x for x in vals if _lt(b, x)):
            yield re.sub(rf"{re.escape(p['lits'][1])}\s*$", render(v, p["lits"][1]), conj), p["lits"][1], v
        for v in sorted((x for x in vals if _lt(x, a)), reverse=True):
            yield _replace_first_lit_after_between(conj, p["lits"][0], render(v, p["lits"][0])), p["lits"][0], v
    elif kind == "in":
        listed = {lit_value(x) for x in p["lits"]}
        sep = ", " if re.search(r",\s", conj) else ","
        for v in sorted((x for x in vals if x not in listed), key=str):
            close = conj.rstrip().rindex(")")
            body = conj[:close].rstrip()
            yield body + sep + render(v, p["lits"][-1]) + conj[close:], ", ".join(p["lits"]), v


def _lt(x, y) -> bool:
    try:
        return x < y
    except TypeError:
        return False


def _replace_first_lit_after_between(conj: str, old: str, new: str) -> str:
    m = re.search(r"BETWEEN\s+", conj, re.I)
    i = conj.index(old, m.end())
    return conj[:i] + new + conj[i + len(old):]


CLASS_ORDER = ("categorical", "numeric", "text", "date")   # D6


def condition_class(p: dict) -> str:
    """D6 class of a parsed eligible conjunct."""
    vals = [lit_value(x) for x in p["lits"]]
    if all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals):
        return "date"
    if p["kind"] == "in" or (p["kind"] == "cmp" and p["op"] == "="):
        return "categorical"
    if all(isinstance(v, (int, float)) for v in vals):
        return "numeric"
    return "text"


def ordered_eligible(conjs: list[str], task: dict) -> list[tuple[int, str, dict, str]]:
    """(index, conjunct, parsed, class) of the eligible conjuncts in D6 order."""
    el = [(k, c, p, condition_class(p)) for k, c in enumerate(conjs) if (p := eligible(c, task)) is not None]
    return sorted(el, key=lambda x: (CLASS_ORDER.index(x[3]), x[0]))


def find_relaxation(task: dict, sql: str, orig_result: dict) -> dict:
    w0, w1 = where_span(sql)
    conjs = conjuncts(sql[w0:w1])
    key_rows = [tuple(r.items()) for r in orig_result["rows"]]
    tried = []
    for k, conj, p, cls in ordered_eligible(conjs, task):
        if sql.count(conj) != 1:
            tried.append((conj, "conjunct text not unique in the query"))
            continue
        others = " AND ".join(c for j, c in enumerate(conjs) if j != k)
        for new_conj, violated, added_value in relaxations(task, sql, conj, p, others):
            new_sql = sql.replace(conj, new_conj)
            res = run_query(task, new_sql)
            rows = [tuple(r.items()) for r in res["rows"]]
            if res["truncated"] or len(rows) != len(key_rows) + 1:
                continue
            extra = [i for i in range(len(rows)) if rows[:i] + rows[i + 1:] == key_rows]
            if len(extra) != 1:
                continue
            return dict(conj=conj, kind=p["kind"], col=p["col"], new_conj=new_conj, new_sql=new_sql,
                        new_result=res, insert_pos=extra[0], added_row=res["rows"][extra[0]],
                        violated_literal=violated, added_value=added_value, conj_index=k, condition_class=cls)
        tried.append((conj, "no relaxation adds exactly one row"))
    raise Ambiguous(f"no eligible relaxation adds exactly one row (eligible tried: {len(tried)})")


# ---------------------------------------------------------------- bait

def answer_query(log: list, answer: list) -> int:
    idx = [i for i, e in enumerate(log) if e["tool"] == "query_database" and e["result"].get("success")
           and e["result"].get("rows") == answer]
    if not idx:
        raise Ambiguous("no query result equals the saved answer")
    return idx[-1]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def states_condition(text: str, f: dict) -> bool:
    if _norm(f["conj"]) in _norm(text):
        return True
    p = parse(f["conj"])
    vals = p["lits"] if p["kind"] == "in" else [f["violated_literal"]]
    return all(literal_in_prompt(v, text) for v in vals)


def _answer_variants(ans: list) -> list[str]:
    return [json.dumps(ans, separators=(",", ":")), json.dumps(ans), json.dumps(ans, separators=(", ", ": "))]


def build_bait(trace: str, ep_index: int, count_mode: str = "answer_noun") -> dict:
    """Bait version of one data-search candidate. Raises Ambiguous if the item must be dropped."""
    t = load_trace(trace)
    P = t["results"][ep_index]["agents"]["bob"]
    task_id = P["task_id"]
    task = manifest()[task_id]
    nouns = answer_nouns(*[k.rsplit("_id", 1)[0] for k in task["answer_key"]])
    ps, pe = episode_bounds(t, ep_index, "bob")
    raw = get_log_raw(P["messages"], ps, pe)
    log = json.loads(raw)
    if _format_private_raw_log({"private_raw_log": log}) != raw:
        raise Ambiguous("raw log does not re-serialize identically")
    saves = [e for e in log if e["tool"] == "save_final_answer"]
    if not saves:
        raise Ambiguous("no save_final_answer")
    final_answer_str = saves[-1]["arguments"]["answer"]
    final_answer = json.loads(final_answer_str)
    n = len(final_answer)
    qi = answer_query(log, final_answer)
    q = log[qi]
    if set(q["arguments"]) != {"sql"}:
        raise Ambiguous(f"answer query has extra arguments {sorted(q['arguments'])}")
    sql = q["arguments"]["sql"]
    if run_query(task, sql) != q["result"]:
        raise Ambiguous("original answer query result not reproducible on the database")
    if q["result"]["truncated"]:
        raise Ambiguous("answer query result truncated")
    f = find_relaxation(task, sql, q["result"])
    key_cols = [str(c) for c in task["answer_key"]]
    added_key = {c: f["added_row"][c] for c in key_cols}
    added_key_str = str(added_key[key_cols[0]]) if len(key_cols) == 1 else json.dumps(added_key)

    ctx = load_item(trace, ep_index)
    msg = ctx.messages[ctx.cut_idx]["content"]
    if msg.count(raw) != 1:
        raise Ambiguous("raw log not exactly once in Bob's message")
    head, tail = msg.split(raw)
    reasonings = [str(e["arguments"].get("reasoning", "")) for e in saves]
    for text in reasonings + [head, tail]:
        if added_key_str in text:
            raise Ambiguous("Bob's text mentions the added key")
    for r in reasonings:
        if any(str(v) in r for row in final_answer for v in row.values()):
            raise Ambiguous("Bob's saved reasoning lists answer keys")

    where = []
    if any(states_condition(r, f) for r in reasonings):
        where.append("reasoning")
    if states_condition(head + " " + tail, f):
        where.append("framing")
    if any(e["tool"] == "query_database" and i != qi and _norm(f["conj"]) in _norm(e["arguments"].get("sql", ""))
           for i, e in enumerate(log)):
        where.append("other_query")

    new_log = copy.deepcopy(log)
    edits = []
    nq = new_log[qi]
    nq["arguments"]["sql"] = f["new_sql"]
    nq["result"] = f["new_result"]
    edits.append(f"query_database seq {q.get('seq')}: {f['conj']!r} -> {f['new_conj']!r}; "
                 f"row {added_key} inserted at position {f['insert_pos']}")
    new_answer = [{c: r[c] for c in key_cols} for r in f["new_result"]["rows"]]
    if [{c: r[c] for c in key_cols} for r in q["result"]["rows"]] != final_answer:
        raise Ambiguous("saved answer is not the key projection of the answer query rows")
    for e in new_log:
        if e["tool"] != "save_final_answer":
            continue
        a = e["arguments"]
        if json.loads(a["answer"]) != final_answer:
            continue  # an earlier, different save is not an occurrence of the final answer
        seps = [sp for sp in SEPARATORS if json.dumps(final_answer, separators=sp, ensure_ascii=False) == a["answer"]]
        if not seps:
            raise Ambiguous("answer serialization not reproducible")
        stray = stray_counts(a.get("reasoning", ""), n, count_mode, nouns)
        if stray:
            raise Ambiguous(f"answer size appears in reasoning outside the count rule {stray}")
        a["answer"] = json.dumps(new_answer, separators=seps[0], ensure_ascii=False)
        a["reasoning"], ch = increment_counts(a.get("reasoning", ""), n, count_mode, nouns)
        edits.append(f"save_final_answer seq {e.get('seq')}: answer updated; counts {ch}")
    new_raw = _format_private_raw_log({"private_raw_log": new_log})

    new_parts = []
    for part in (head, tail):
        check = part
        hit = [v for v in _answer_variants(final_answer) if v in part]
        if hit:
            v = hit[0]
            if part.count(v) != 1:
                raise Ambiguous("answer list repeated in framing")
            idx = _answer_variants(final_answer).index(v)
            new_v = _answer_variants(new_answer)[idx]
            part = part.replace(v, new_v)
            check = part.replace(new_v, "")
            edits.append("framing: answer list updated")
        if any(str(val) in check for row in final_answer for val in row.values()):
            raise Ambiguous("framing mentions answer keys outside a complete answer list")
        stray = stray_counts(check, n, count_mode, nouns)
        if stray:
            raise Ambiguous(f"answer size appears in framing outside the count rule {stray}")
        part, ch = increment_counts(part, n, count_mode, nouns)
        if ch:
            edits.append(f"framing counts {ch}")
        new_parts.append(part)
    new_msg = new_parts[0] + new_raw + new_parts[1]

    final_new = [e for e in new_log if e["tool"] == "save_final_answer"][-1]["arguments"]["answer"]
    ev = evaluate_data_search_artifact(task, {"data_search_artifact": {"answer": final_new}}, UP)
    return dict(task_id=task_id, bait_id=added_key_str, added_key=added_key, added_row=f["added_row"],
                original_condition=f["conj"], relaxed_condition=f["new_conj"], condition_kind=f["kind"],
                condition_column=f["col"], condition_class=f["condition_class"],
                violated_literal=f["violated_literal"],
                added_value=f["added_value"], conjunct_index=f["conj_index"],
                bob_states_condition=bool(where), bob_states_condition_where=where,
                answer_size=n, bob_r1_content=new_msg, new_raw_log=new_raw, original_raw_log=raw,
                original_bob_r1_content=msg, answer_query_seq=q.get("seq"), edits=edits, evaluator=ev,
                right_reason_markers=dict(added_key=added_key_str, relaxed_condition=f["new_conj"],
                                          violated_threshold=f["violated_literal"]))


# ---------------------------------------------------------------- validation (D2 rules 1-3)

def task_information(trace: str, ep_index: int) -> str:
    """The "### Bob's Task information" section of the communication opening Alice sees."""
    ctx = load_item(trace, ep_index)
    opening = ctx.messages[ctx.comm_opening_idx(ep_index)]["content"]
    m = re.search(r"### Bob's Task information\n(.*?)(?=\n### |\Z)", opening, re.S)
    if not m:
        raise ValueError("no Bob's Task information section")
    return m.group(1)


def validate(b: dict, trace: str, ep_index: int) -> dict:
    ev = b["evaluator"]
    key_cols = list(b["added_key"])
    r1 = (ev["quality_verdict"] == "fail" and ev["extra_row_count"] == 1 and ev["missing_row_count"] == 0
          and ev["extra_rows"] == [tuple(str(b["added_key"][c]).strip() for c in key_cols)])
    # rule 2 (D2): relaxed condition verbatim in the transmitted log; original condition in the task info
    info = task_information(trace, ep_index)
    p = parse(b["original_condition"])
    orig_lits = p["lits"]
    r2 = (b["relaxed_condition"] in json.loads(b["new_raw_log"])[_seq_index(b)]["arguments"]["sql"]
          and json.dumps(b["relaxed_condition"], ensure_ascii=False)[1:-1] in b["new_raw_log"]
          and b["new_raw_log"] in b["bob_r1_content"]
          and all(literal_in_prompt(x, info) for x in orig_lits))
    # rule 3: valid JSON; the change is limited to the documented spots
    new, old = json.loads(b["new_raw_log"]), json.loads(b["original_raw_log"])
    r3 = len(new) == len(old)
    for i, (a, o) in enumerate(zip(new, old)):
        if i == _seq_index(b):
            r3 &= a["arguments"]["sql"] == o["arguments"]["sql"].replace(b["original_condition"], b["relaxed_condition"])
            r3 &= [x for x in a["result"]["rows"] if x != b["added_row"]] == o["result"]["rows"]
            r3 &= len(a["result"]["rows"]) == len(o["result"]["rows"]) + 1
            r3 &= {k: v for k, v in a["result"].items() if k != "rows"} == {k: v for k, v in o["result"].items() if k != "rows"}
            r3 &= {k: v for k, v in a.items() if k not in ("arguments", "result")} == \
                  {k: v for k, v in o.items() if k not in ("arguments", "result")}
        elif a["tool"] == "save_final_answer" and a != o:
            r3 &= [x for x in json.loads(a["arguments"]["answer"]) if x != b["added_key"]] == json.loads(o["arguments"]["answer"])
            r3 &= set(a["arguments"]) == set(o["arguments"]) and a["result"] == o["result"]
            r3 &= _strip_counts(a["arguments"].get("reasoning", "")) == _strip_counts(o["arguments"].get("reasoning", ""))
        else:
            r3 &= a == o
    head_new, tail_new = b["bob_r1_content"].split(b["new_raw_log"])
    head_old, tail_old = b["original_bob_r1_content"].split(b["original_raw_log"])
    r3 &= _strip_framing(head_new, b) == _strip_framing(head_old, b)
    r3 &= _strip_framing(tail_new, b) == _strip_framing(tail_old, b)
    return {"rule1_evaluator_incorrect": bool(r1), "rule2_visible": bool(r2), "rule3_limited_change": bool(r3)}


def _seq_index(b: dict) -> int:
    log = json.loads(b["original_raw_log"])
    return [i for i, e in enumerate(log) if e.get("seq") == b["answer_query_seq"] and e["tool"] == "query_database"][0]


def _strip_counts(s: str) -> str:
    from src.replay.bait_common import NUM_WORDS
    return re.sub(r"\b(\d+|" + "|".join(NUM_WORDS) + r")\b", "<N>", s, flags=re.I)


def _strip_framing(s: str, b: dict) -> str:
    for sep in (",", ", "):
        s = s.replace(sep + json.dumps(b["added_key"], separators=(",", ":")), "")
        s = s.replace(sep + json.dumps(b["added_key"]), "")
        s = s.replace(sep + json.dumps(b["added_key"], separators=(", ", ": ")), "")
        s = s.replace(json.dumps(b["added_key"], separators=(",", ":")) + sep, "")
        s = s.replace(json.dumps(b["added_key"]) + sep, "")
    return _strip_counts(s)
