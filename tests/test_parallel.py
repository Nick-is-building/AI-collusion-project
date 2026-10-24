"""Process-parallel launcher (src/runner/parallel.py), mock mode only."""
import json
import shutil
from pathlib import Path

from src.runner.costs import Ledger
from src.runner.parallel import assign, run_parallel, split_caps

OUT = Path(__file__).resolve().parents[1] / "scratch" / "pytest_parallel"


def small_jobs():
    from src.runner.item_lists import p5_items
    from src.runner.jobs import make_job
    return [make_job("PT", r, v, "bait") for r in p5_items().head(3).itertuples() for v in ("R4", "R4n")]


def test_assign_keeps_items_together():
    jobs = small_jobs()
    parts = [assign(jobs, k, 2) for k in range(2)]
    assert sum(len(p) for p in parts) == len(jobs)
    assert not ({j.item_id for j in parts[0]} & {j.item_id for j in parts[1]})


def test_split_caps_sum_never_exceeds_cap(tmp_path):
    caps = {"hard_cap_usd": 250.0, "stages": {"pilot": 10.0},
            "check_groups": {"g": {"stage": "pilot", "checks": ["P1"], "cap_usd": 2.0}}}
    led = Ledger(tmp_path, "live")
    led.add("pilot", 4.0, check="P1")
    s = split_caps(caps, led, "pilot", 4)
    assert abs(4.0 + 4 * (s["stages"]["pilot"] - 4.0) - 10.0) < 1e-9
    assert abs(4.0 + 4 * (s["check_groups"]["g"]["cap_usd"] - 4.0) - 4.0) < 1e-9   # group already over: no headroom


def test_run_parallel_mock_resumable():
    shutil.rmtree(OUT, ignore_errors=True)
    st = run_parallel("tests.test_parallel:small_jobs", 2, stage="pilot", mode="mock", results_dir=OUT / "raw",
                      requests_dir=OUT / "req")
    assert sum(s["completed"] for s in st) == 6
    st2 = run_parallel("tests.test_parallel:small_jobs", 2, stage="pilot", mode="mock", results_dir=OUT / "raw",
                       requests_dir=OUT / "req")
    assert sum(s["completed"] for s in st2) == 0     # resume: nothing redone
    ids = [json.loads(l)["call_id"] for f in (OUT / "raw").glob("*.jsonl") for l in f.read_text().splitlines()
           if json.loads(l)["type"] == "call"]
    assert len(ids) == len(set(ids)) == 6
    shutil.rmtree(OUT)
