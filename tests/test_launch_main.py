"""Main-run launcher stage 1 and operational monitor (A04 task 3)."""
import collections

from scripts.main.launch_main import first_jobs
from scripts.main.monitor import summary
from src.runner.jobs import main_run_jobs

VARIANTS = {"R0", "R0p", "R1", "R2", "R3", "R4", "R4n", "R5", "R6", "N1", "N4", "FR0"}


def test_first_stage_is_prefix_blocks_of_frozen_list():
    full = [j.call_id("main") for j in main_run_jobs()]
    first = [j.call_id("main") for j in first_jobs()]
    assert len(first) == len(set(first)) == 5 * 19 + 5 * 2 + 2 * 3
    assert set(first) <= set(full)
    pos = [full.index(c) for c in first]
    assert pos == sorted(pos)                       # same order as the frozen list
    per_variant = collections.Counter(c.split(":")[3] for c in first)
    assert set(per_variant) == VARIANTS and min(per_variant.values()) >= 5
    items = collections.defaultdict(set)            # complete item blocks: every call of a chosen item
    for c in first:
        items[c.split(":")[2]].add(c)
    for item, cs in items.items():
        assert {c for c in full if c.split(":")[2] == item} >= cs


def test_monitor_prints_no_verdicts():
    calls = [{"type": "call", "call_id": "main:MAIN:x:R1:bait:1", "variant": "R1", "verdict_status": "ok",
              "verdict": "reject", "cost_usd": 0.01, "response_models": ["m"], "n_rate_limit": 1,
              "api_error_counts": {"transient_rate_limit": 1}, "ts_end_utc": "t"}]
    s = summary(calls, [], ["main:MAIN:x:R1:bait:1", "main:MAIN:x:R1:bait:2"], 40.0)
    assert s["per_variant"]["R1"] == {"done": 1, "ok": 1, "expected": 2}
    assert "reject" not in str(s) and "accept" not in str(s)
