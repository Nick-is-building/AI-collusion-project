"""P10 cost and wall-time projection for the main run (plan sections 10, 12; A03 task 4). Makes no call.

Main-run list: src.runner.jobs.main_run_jobs() (109 main items x 19 calls incl. the second draws of
the four primary cells, N1/N4 on 35 natural-error items, R0 x 3 on 63 fidelity cases). Not included:
R1-live, Haiku, Gemini 3.7 Flash (not built / not authorized).

Input tokens per call (request as sent):
  R0, FR0     original logged input_tokens - 5 x unmatched resolve_records items (A03 task 1; exact
              for 30/30 pilot items); fidelity/natural items without an unmatched count use the original
  R1, R0', R6 countTokens of the cut context (data/derived/r5_fillers.csv, count_R1_or_R0p; exact)
  R4, R5      countTokens (count_R4, count_R5; exact)
  R2, R3, R4n count(CUT or R4) x chars(variant) / chars(CUT or R4) (signature-stripped characters;
              estimate)
  N1, N4      src.runner.estimates.input_tokens (character-ratio estimate from the original tokens)
Measured from live pilot calls (results/raw, stage pilot), per variant group with a pooled fallback:
  output tokens per call (billable, all attempts), API requests per call, input-token multiplier of R6
  (all requests of the call / first request), cached-input share, wall seconds per call.
Cost: Flash-Lite prices (configs/prices.yaml); two figures: no cache savings (plan 12, conservative)
and with the measured cached share. Wall time: sum of measured seconds per call / parallelism
(no rate-limit model; 429 counts of the pilot reported).

  .venv/bin/python -m scripts.pilot.p10_cost
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.runner.costs import PriceTable, iter_call_lines, load_yaml
from src.runner.estimates import input_tokens, nosig_chars, r0_tokens

ROOT = Path(__file__).resolve().parents[2]
FL = "gemini/gemini-3.1-flash-lite"
GROUP = {"R0": "R0", "FR0": "R0", "R0p": "CUT", "R1": "CUT", "CUT": "CUT", "N1": "CUT", "R2": "R2", "R3": "R3",
         "R4": "R4", "R4n": "R4", "N4": "R4", "R5": "R5", "R6": "R6"}


def _ts(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")


def measured(results_dir=ROOT / "results" / "raw", mode: str = "live") -> pd.DataFrame:
    rows = []
    for r in iter_call_lines(results_dir):
        if r.get("mode") != mode:
            continue
        if r.get("model") != FL or r.get("check") in ("P1",):
            continue
        u = r["usage"]
        first_in = next((x.get("input_tokens") for x in u if x.get("input_tokens")), None)
        tot_in = sum(x.get("input_tokens") or 0 for x in u)
        rows.append(dict(check=r["check"], variant=r["variant"], group=GROUP.get(r["variant"], r["variant"]),
                         n_req=r["n_api_requests"], first_in=first_in, tot_in=tot_in,
                         cached=sum(x.get("cached_input_tokens") or 0 for x in u),
                         out=sum((x.get("billable_output_tokens") if x.get("billable_output_tokens") is not None
                                  else x.get("provider_output_tokens") or 0) for x in u),
                         sec=(_ts(r["ts_end_utc"]) - _ts(r["ts_start_utc"])).total_seconds(),
                         n429=r.get("n_rate_limit", 0), cost=r.get("cost_usd") or 0.0, status=r["verdict_status"]))
    return pd.DataFrame(rows)


def per_group(m: pd.DataFrame) -> dict:
    pooled = dict(out=m.out.mean(), n_req=m.n_req.mean(), mult=1.0, cache=m.cached.sum() / m.tot_in.sum(),
                  sec=m.sec.mean(), n=len(m))
    out = {"pooled": pooled}
    for g, d in m.groupby("group"):
        out[g] = dict(out=d.out.mean(), n_req=d.n_req.mean(), mult=(d.tot_in / d.first_in).mean(),
                      cache=d.cached.sum() / d.tot_in.sum(), sec=d.sec.mean(), n=len(d))
    return out


def job_tokens(job, r5: dict, unmatched: dict) -> tuple[int, str]:
    v, item = job.variant, job.item_id
    if v in ("R0", "FR0"):
        return r0_tokens()[item] - 5 * unmatched.get(item, 0), "exact"
    key = (item, job.version)
    if key in r5:
        c = r5[key]
        if v in ("R1", "R0p", "R6"):
            return c["count_R1_or_R0p"], "exact"
        if v == "R4":
            return c["count_R4"], "exact"
        if v == "R5":
            return c["count_R5"], "exact"
        if v in ("R2", "R3"):
            return int(round(c["count_R1_or_R0p"] * nosig_chars(item, v) / nosig_chars(item, "CUT"))), "ratio"
        if v == "R4n":
            return int(round(c["count_R4"] * nosig_chars(item, "R4n") / nosig_chars(item, "R4"))), "ratio"
    est = {"N1": "CUT", "N4": "R4"}.get(v, v)
    return input_tokens(item, est), "estimate"


def projection(jobs=None, m: pd.DataFrame | None = None, prices=None) -> dict:
    from src.runner.jobs import R5_TABLE, main_run_jobs
    prices = prices or PriceTable()
    jobs = jobs if jobs is not None else main_run_jobs()
    m = measured() if m is None else m
    g = per_group(m)
    r5 = {(r.item_id, r.version): r._asdict() for r in pd.read_csv(R5_TABLE).itertuples()}
    un = dict(pd.read_csv(ROOT / "data" / "derived" / "r0_unmatched_records.csv")[["item_id", "n_unmatched"]].values)
    rows = []
    for j in jobs:
        tok, src = job_tokens(j, r5, un)
        st = g.get(GROUP.get(j.variant, j.variant), g["pooled"])
        n_req = max(st["n_req"], 1.0)
        tot_in = tok * (st["mult"] if j.variant == "R6" else n_req)
        out = st["out"]
        nocache = prices.cost(FL, int(tot_in), 0, int(out))
        cache = prices.cost(FL, int(tot_in), int(tot_in * st["cache"]), int(out))
        rows.append(dict(variant=j.variant, version=j.version, draw=j.draw, tokens=tok, source=src, tot_in=tot_in,
                         out=out, usd_nocache=nocache, usd_cache=cache, sec=st["sec"]))
    d = pd.DataFrame(rows)
    second = (d.draw == 2) & d.variant.isin(["R1", "R0p", "R4"])   # second draws of the four primary cells
    summary = dict(calls=len(d), input_tokens=int(d.tot_in.sum()), usd_nocache=float(d.usd_nocache.sum()),
                   usd_cache=float(d.usd_cache.sum()), second_draw_calls=int(second.sum()),
                   second_draw_usd_nocache=float(d[second].usd_nocache.sum()),
                   sequential_hours=float(d.sec.sum() / 3600), token_sources=d.source.value_counts().to_dict(),
                   by_variant=d.groupby("variant").agg(calls=("variant", "size"), usd_nocache=("usd_nocache", "sum"),
                                                       usd_cache=("usd_cache", "sum"), mean_tokens=("tokens", "mean"))
                   .round(3).reset_index().to_dict("records"))
    for p in (1, 4, 8, 16):
        summary[f"wall_hours_parallel_{p}"] = summary["sequential_hours"] / p
        summary[f"input_tpm_parallel_{p}"] = summary["input_tokens"] / max(d.sec.sum() / p / 60, 1e-9)
    summary["measured"] = {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                           for k, v in g.items()}
    summary["pilot_429"] = int(m.n429.sum())
    summary["pilot_missing"] = int((m.status != "ok").sum())
    summary["hard_cap_usd"] = load_yaml("caps.yaml")["hard_cap_usd"]
    return summary


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(ROOT / "results" / "raw"), help="measured pilot calls")
    ap.add_argument("--out", default=str(ROOT / "results" / "summaries" / "p10_projection.json"))
    ap.add_argument("--mode", default="live", help="mode of the measured calls (mock only for tests)")
    a = ap.parse_args(argv)
    s = projection(m=measured(Path(a.results_dir), a.mode))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(s, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(json.dumps({k: v for k, v in s.items() if k not in ("by_variant", "measured")}, indent=1,
                     default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(pd.DataFrame(s["by_variant"]).to_string())
    return s


if __name__ == "__main__":
    main()
