"""Process-parallel execution of a job list (A03; needed for P10's wall time at a given parallelism).

Threads are not safe here: `run_verdict` swaps the module-global `experiments.agents.completion`
(request recorder) and R6 swaps `experiments.agents.get_tool_schemas` for the duration of a call, so
concurrent threads would mix requests between calls. Each worker is therefore a separate process
(spawn) with its own module globals.

- Jobs contain closures and are not pickled: every worker rebuilds the job list from `factory`
  ("module:function", called with no arguments) and keeps the items assigned to it: unique item_ids in
  first-appearance order, item k goes to worker k mod n (all calls of an item stay in one worker, in
  the list's order).
- Each worker is a normal `Runner` (own run ID and JSONL file, resumable by call ID).
- Caps stay fail-closed in total: at launch the remaining headroom of every cap (stage, hard cap, and
  check groups) is computed once from the ledger and split equally; worker w's cap = spent at launch +
  headroom / n. The sum over workers can therefore not exceed the configured cap.
"""
from __future__ import annotations

import importlib
import multiprocessing as mp
from pathlib import Path

from src.runner.costs import Ledger, load_yaml


def _resolve(factory: str):
    mod, fn = factory.split(":")
    return getattr(importlib.import_module(mod), fn)


def split_caps(caps: dict, ledger: Ledger, stage: str, n: int) -> dict:
    out = {"hard_cap_usd": ledger.total + (caps["hard_cap_usd"] - ledger.total) / n,
           "stages": {stage: ledger.by_stage.get(stage, 0.0) + (caps["stages"][stage] - ledger.by_stage.get(stage, 0.0)) / n},
           "check_groups": {}}
    for name, g in (caps.get("check_groups") or {}).items():
        spent = ledger.group_spent(g)
        out["check_groups"][name] = dict(g, cap_usd=spent + max(g["cap_usd"] - spent, 0.0) / n)
    return out


def assign(jobs: list, k: int, n: int) -> list:
    order = list(dict.fromkeys(j.item_id for j in jobs))
    mine = {item for i, item in enumerate(order) if i % n == k}
    return [j for j in jobs if j.item_id in mine]


def _worker(args):
    factory, k, n, stage, mode, results_dir, requests_dir, approved_stage, seed, caps = args
    from src.runner.runner import Runner
    jobs = assign(_resolve(factory)(), k, n)
    backend = None
    if mode == "mock":
        from src.replay.request import mock_backend
        backend = mock_backend()
    r = Runner(stage=stage, mode=mode, results_dir=Path(results_dir), requests_dir=Path(requests_dir), backend=backend,
               approved_stage=approved_stage, seed=seed, caps=caps,
               log=lambda s: print(f"[worker {k}/{n}] {s}", flush=True))
    stats = r.run(jobs)
    stats["run_path"] = str(r.path)
    return stats


def run_parallel(factory: str, n: int, *, stage: str, mode: str, results_dir, requests_dir,
                 approved_stage: str | None = None, seed: int | None = None) -> list[dict]:
    caps = split_caps(load_yaml("caps.yaml"), Ledger(Path(results_dir), mode), stage, n)
    args = [(factory, k, n, stage, mode, str(results_dir), str(requests_dir), approved_stage, seed, caps)
            for k in range(n)]
    if n == 1:
        return [_worker(args[0])]
    with mp.get_context("spawn").Pool(n) as pool:
        return pool.map(_worker, args)
