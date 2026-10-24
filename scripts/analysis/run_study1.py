"""One script for all Study 1 numbers (plan 23.4): reads the raw JSONL call lines and writes
results/summaries/study1_analysis.json (and prints the headline numbers).

  .venv/bin/python -m scripts.analysis.run_study1 [--results-dir results/raw] [--stage main] [--check MAIN]
"""
import argparse
from pathlib import Path

import pandas as pd

from src.analysis.fidelity import ROOT_UNMATCHED, level1, level2
from src.analysis.meta import main_meta, natural_meta
from src.analysis.primary import analyze, load_calls, to_json
from src.runner.costs import iter_call_lines
from src.runner.estimates import r0_tokens

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(ROOT / "results" / "raw"))
    ap.add_argument("--stage", default="main")
    ap.add_argument("--check", default="MAIN")
    ap.add_argument("--mode", default="live")
    ap.add_argument("--out", default=str(ROOT / "results" / "summaries" / "study1_analysis.json"))
    a = ap.parse_args(argv)
    calls = load_calls(a.results_dir, a.stage, a.check, a.mode)
    if calls.empty:
        print("no calls")
        return None
    res = analyze(calls, main_meta(), natural_meta())
    recs = [r for r in iter_call_lines(Path(a.results_dir)) if r.get("stage") == a.stage and r.get("mode") == a.mode]
    res["fidelity_level1"] = level1(recs, r0_tokens(), pd.read_csv(ROOT / ROOT_UNMATCHED))
    res["fidelity_level2"] = level2(calls, pd.read_csv(ROOT / "data" / "derived" / "items" / "fidelity_set.csv"))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(to_json(res))
    p = res["primary"]
    print("Delta", p["Delta_R4_minus_R1"], "\nD", p["D"], "\nclaim:", p["claim"])
    return res


if __name__ == "__main__":
    main()
