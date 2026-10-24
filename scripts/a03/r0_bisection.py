"""A03 task 1: token bisection of the R0 identity mismatches (plan section 8.7, level 1).

Stage "calibrate": countTokens on the R0 request of 2 exact-match items and the 7 mismatched items;
countTokens must reproduce the input_tokens the live API reported in P2/P9.
Stage "episodes": for each mismatched item, countTokens on the verdict request of every earlier
episode of the same judge (built by the same builder as R0, `variants.build(load_item(trace, k,
judge), "R0")`), compared with that episode's logged verdict input_tokens. The first episode with a
nonzero difference localizes the discrepancy.

  set -a; . ./.env; set +a; .venv/bin/python -m scripts.a03.r0_bisection --stage calibrate --live
"""
import argparse
import json

from src.replay.token_count import count_tokens, http_body, request_kwargs
from src.replay.traces import load_trace, verdict_usage
from src.replay.variants import build, load_item

MISMATCH = {  # item: API-reported input_tokens in P2/P9 (results/raw/pilot-*.jsonl)
    "rep022_e07_alice": None, "rep009_e02_alice": None, "rep014_e09_bob": None, "rep047_e10_bob": None,
    "rep003_e02_bob": None, "rep007_e09_bob": None, "rep007_e09_alice": None}
EXACT = ["rep002_e03_alice", "rep004_e02_alice"]


def parse(item):
    rep, ep, judge = item.split("_")
    return f"{rep}.json.gz", int(ep[1:]) - 1, judge


def logged(trace, k, judge):
    use = verdict_usage(load_trace(trace), k, judge)
    acc = [u for u in use if u.get("response_status") == "accepted"] or use
    return acc[0]["input_tokens"]


def api_reported():
    from src.runner.costs import iter_call_lines
    out = {}
    for r in iter_call_lines("results/raw"):
        if r.get("variant") == "R0" and r.get("mode") == "live":
            acc = [u for u in r["usage"] if u.get("response_status") == "accepted"]
            if acc:
                out.setdefault(r["item_id"], set()).add(acc[0]["input_tokens"])
    return out


def count_r0(trace, k, judge, live, label):
    t = load_trace(trace)
    msgs = build(load_item(trace, k, judge), "R0")
    url, body = http_body(request_kwargs(msgs, t["results"][k]["task_type"], judge=judge))
    return count_tokens(body, url, purpose="r0_bisection", label=label, live=live)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["calibrate", "episodes", "calls"], required=True)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    if a.stage == "calls":
        return stage_calls(a.live)
    api = api_reported()
    out = []
    if a.stage == "calibrate":
        for item in EXACT + list(MISMATCH):
            tr, k, j = parse(item)
            n = count_r0(tr, k, j, a.live, f"calibrate:{item}")
            row = dict(item=item, count_tokens=n, logged=logged(tr, k, j), api=sorted(api.get(item, [])))
            print(row)
            out.append(row)
    else:
        for item in MISMATCH:
            tr, k_end, j = parse(item)
            for k in range(1 if j == "alice" else 0, k_end + 1):
                try:
                    n = count_r0(tr, k, j, a.live, f"episodes:{item}:ep{k}")
                except AssertionError:
                    print(item, k, "no single verdict prompt; skipped")
                    continue
                lg = logged(tr, k, j)
                row = dict(item=item, ep_index=k, count_tokens=n, logged=lg, diff=n - lg)
                print(row)
                out.append(row)
    p = f"scratch/a03/bisection_{a.stage}.json"
    open(p, "w").write(json.dumps(out, indent=1))



# ---- stage "calls": within-episode localization (appended after the episode stage) ----------------
FIRST_BAD = {"rep022_e07_alice": 6, "rep009_e02_alice": 1, "rep014_e09_bob": 0, "rep047_e10_bob": 2,
             "rep003_e02_bob": 1, "rep007_e09_bob": 1, "rep007_e09_alice": 8}


def episode_calls(trace, k, judge):
    """(usage record, message-prefix end index) per accepted call of `judge` in episode k, in order."""
    from src.replay.traces import episode_bounds
    t = load_trace(trace)
    msgs = t["results"][k]["agents"][judge]["messages"]
    s, e = episode_bounds(t, k, judge)
    if k == 0:
        s = 1
    asst = [i for i in range(s, e) if msgs[i]["role"] == "assistant"]
    use = [u for u in t["results"][k]["llm_usage"] if u.get("actor") == judge
           and u.get("response_status") == "accepted"]
    assert len(asst) == len(use), (trace, k, judge, len(asst), len(use))
    return msgs, list(zip(use, asst))


def count_prefix(msgs, end, live, label):
    """System + contents only (no tools): kwargs of a plain completion on msgs[:end]."""
    import copy
    kw = dict(model="gemini/gemini-3.1-flash-lite", messages=copy.deepcopy(msgs[:end]), temperature=1.0,
              max_tokens=64000, reasoning_effort="high")
    url, body = http_body(kw)
    return count_tokens(body, url, purpose="r0_bisection", label=label, live=live)


def stage_calls(live):
    out = []
    for item, kb in FIRST_BAD.items():
        tr, _, j = parse(item)
        for k in ([kb - 1] if kb > 0 else []) + [kb]:
            msgs, calls = episode_calls(tr, k, j)
            for n, (u, ai) in enumerate(calls):
                c = count_prefix(msgs, ai, live, f"calls:{item}:ep{k}:{n}")
                row = dict(item=item, ep_index=k, ref=k != kb, n=n, phase=u["phase"], round=u.get("round"),
                           msg_end=ai, count_nt=c, logged=u["input_tokens"], diff=c - u["input_tokens"])
                print(row)
                out.append(row)
    open("scratch/a03/bisection_calls.json", "w").write(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
