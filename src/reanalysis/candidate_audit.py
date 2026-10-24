"""Independent re-derivation of the replay-candidate figures (plan section 8.1, assignment A01 task 2).

Implements the sampling frame from the plan text, not by reusing audit_replay.py:
judge = Alice; Bob's complete raw log (his get_log result in the same episode) is contained
verbatim in his round-1 message; episode >= 2; Bob's task correct (true_expected_verdict = pass);
task type record extraction or data search. The natural-error set uses the same frame with
Bob's task incorrect and any task type.

Usage: .venv/bin/python -m src.reanalysis.candidate_audit [--out data/derived/candidates_audit.csv]
"""
from __future__ import annotations

import argparse
import re
import statistics

import pandas as pd

from src.replay.traces import (ROUND_INSTRUCTION, episode_bounds, get_log_raw, load_trace, trace_files,
                               verdict_contexts, verdict_usage)

FAMILIES = ("record_extraction", "data_search")
COMMIT = re.compile(r"accept|approve|trust|looks? (good|correct)|we('ll| will) both|agree", re.I)


def frame_rows():
    rows = []
    for f in trace_files():
        t = load_trace(f.name)
        for v in verdict_contexts(f.name):
            if v.judge != "alice" or v.ep_index < 1 or v.verdict_prompt_idx is None:
                continue
            msgs = t["results"][v.ep_index]["agents"]["alice"]["messages"]
            r1 = [i for i in v.peer_msg_idx if msgs[i]["content"].startswith("[round=1/")]
            if len(r1) != 1 or not v.peer_raw_log or v.peer_raw_log not in msgs[r1[0]]["content"]:
                continue
            cut = r1[0]
            vp = v.verdict_prompt_idx
            ctx = msgs[:vp + 1]
            consec_any = any(ctx[i]["role"] == "user" and ctx[i + 1]["role"] == "user"
                             for i in range(len(ctx) - 1))
            consec_peer_vp = msgs[vp - 1]["role"] == "user" and "[from=bob]" in str(msgs[vp - 1]["content"])
            use = verdict_usage(t, v.ep_index, "alice")
            acc = [u for u in use if u.get("response_status") == "accepted"]
            P = t["results"][v.ep_index]["agents"]["bob"]
            ee = P.get("extraction_eval") or {}
            de = P.get("data_search_eval") or {}
            # Alice's own send_message contents before the cut (for the phrase search)
            sends = []
            for m in msgs[v.ep_start:cut]:
                for c in (m.get("tool_calls") or []) if m["role"] == "assistant" else []:
                    if c["function"]["name"] == "send_message":
                        a = c["function"]["arguments"]
                        a = __import__("json").loads(a) if isinstance(a, str) else a
                        sends.append(a.get("content", ""))
            # as in the pre-sprint audit: Alice's own raw log is removed before the phrase search,
            # because log content (e.g. "approved_exception") is task data, not a statement
            own_raw = get_log_raw(msgs, *episode_bounds(t, v.ep_index, "alice")) or "@@"
            rows.append(dict(
                trace=v.trace, run_id=v.run_id, ep_index=v.ep_index, evaluation_episode=v.evaluation_episode,
                task_type=v.task_type, peer_task_id=P.get("task_id"), peer_correct=v.peer_correct,
                verdict=v.verdict, cut_idx=cut, verdict_prompt_idx=vp,
                cut_msg_starts_round1_bob=msgs[cut]["content"].startswith("[round=1/5][from=bob]"),
                cut_msg_has_round_instruction=bool(ROUND_INSTRUCTION.search(msgs[cut]["content"])),
                cut_msg_role=msgs[cut]["role"],
                consecutive_user_any=consec_any, bob_msg_directly_before_verdict_prompt=consec_peer_vp,
                n_verdict_usage=len(use), n_verdict_accepted=len(acc),
                verdict_input_tokens=(acc[0] if acc else use[0])["input_tokens"] if use else None,
                verdict_input_tokens_first=use[0]["input_tokens"] if use else None,
                response_model=(acc[0] if acc else use[0]).get("response_model") if use else None,
                phrase_match_before_cut=any(COMMIT.search(s.replace(own_raw, "")) for s in sends),
                phrase_match_incl_own_log=any(COMMIT.search(s) for s in sends),
                ext_missing=len(ee.get("missing_references") or []), ext_extra=len(ee.get("extra_references") or []),
                ds_missing=de.get("missing_row_count"), ds_extra=de.get("extra_row_count"),
            ))
    return pd.DataFrame(rows)


def condition_counts():
    """REJECT count over all verdicts, and correct peer tasks whose raw log was strictly fully
    transmitted (strict_full, src/reanalysis/transmission.py), both judges, from the raw traces."""
    from src.reanalysis.transmission import strict_full
    rej = cl = 0
    for f in trace_files():
        t = load_trace(f.name)
        for v in verdict_contexts(f.name):
            rej += v.verdict == "reject"
            if v.peer_correct and v.peer_raw_log:
                msgs = [m["content"] for m in t["results"][v.ep_index]["channel_transcript"]
                        if m["sender"] == v.peer]
                cl += strict_full(v.peer_raw_log, msgs)
    return rej, cl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    d = frame_rows()
    c = d[d.peer_correct & d.task_type.isin(FAMILIES)]
    n = d[~d.peer_correct]
    print(f"candidates: {len(c)} {c.task_type.value_counts().to_dict()}  trajectories: {c.trace.nunique()}"
          f"  max per trajectory: {c.groupby('trace').size().max()}")
    tok = c.verdict_input_tokens.astype(int)
    print(f"verdict input tokens (accepted call): median {statistics.median(tok)}  max {tok.max()}"
          f"  share > 100000: {(tok > 100000).mean():.3f} ({(tok > 100000).sum()}/{len(tok)})")
    print(f"  calls with >1 verdict usage entry: {(c.n_verdict_usage > 1).sum()}; first-entry median"
          f" {statistics.median(c.verdict_input_tokens_first.astype(int))}")
    print(f"phrase matches in Alice's sends before the cut (own raw log removed): {int(c.phrase_match_before_cut.sum())}"
          f"; without removing it: {int(c.phrase_match_incl_own_log.sum())}")
    print(f"cut message starts '[round=1/5][from=bob]': {int(c.cut_msg_starts_round1_bob.sum())}/{len(c)};"
          f" role user: {int((c.cut_msg_role == 'user').sum())}; contains round instruction:"
          f" {int(c.cut_msg_has_round_instruction.sum())}")
    print(f"consecutive user messages anywhere in original verdict context: {int(c.consecutive_user_any.sum())}/{len(c)};"
          f" Bob message directly before verdict prompt: {int(c.bob_msg_directly_before_verdict_prompt.sum())}/{len(c)}")
    print(f"natural-error set: {len(n)} {n.task_type.value_counts().to_dict()}")
    ne = n[n.task_type == "record_extraction"]
    om = ((ne.ext_missing > 0) & (ne.ext_extra == 0)).sum()
    co = ((ne.ext_missing == 0) & (ne.ext_extra > 0)).sum()
    bo = ((ne.ext_missing > 0) & (ne.ext_extra > 0)).sum()
    print(f"  extraction: omission {om}, commission {co}, both {bo}, neither {len(ne) - om - co - bo}")
    rej, cl = condition_counts()
    print(f"original REJECT verdicts in the condition (all judges, all episodes): {rej}")
    print(f"correct peer tasks with a strictly complete log (both judges): {cl}")
    if args.out:
        d.to_csv(args.out, index=False)
        print("written", args.out)
    return d


if __name__ == "__main__":
    main()
