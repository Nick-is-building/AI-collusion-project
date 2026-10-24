"""Fail-closed cost and model guard for Study 2 runs (plan sections 12, 13, 23.2; D20).

Upstream has no cost cap and no model-change stop. Every Study 2 process replaces
`experiments.agents.completion` (the single call site of the model) with a guarded function that,
before each API request:
  1. stops if the shared STOP file exists (written on a model change or by the operator);
  2. checks the ledger: spend so far + a reserve for the calls that may be in flight in all
     workers must stay within the check-group cap (P8: 5 USD), the Study 2 stage cap and the
     project hard cap (configs/caps.yaml);
and after each response checks `response_model` against the expected model (plan 8.5, 13).

Stops raise Study2Stop, a BaseException: upstream's retry loop catches `Exception` and would
otherwise retry a cap stop as a transient error (`agents._complete_with_retries`).

Spend is computed with our price table (configs/prices.yaml, src/runner/costs.py) from the
usage records in every upstream per-run journal (`llm_usage.jsonl`, append + fsync per
call) under the Study 2 results root. Branch `run.json` files re-sum copied prefix usage, so they
are never used for cost. Project spend outside Study 2 comes from the existing ledger over
`results/raw` (live mode).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src.runner.costs import Ledger, PriceTable

ROOT = Path(__file__).resolve().parents[2]
STAGE = "study2"
JOURNAL = "llm_usage.jsonl"   # experiments.usage.LLM_USAGE_JOURNAL_FILENAME (checked in tests)


class Study2Stop(BaseException):
    """Fail-closed stop (cap, model change, STOP file). Not an Exception on purpose."""


class JournalLedger:
    """Incremental spend over all journals under `root`, split by first path component (group)."""

    def __init__(self, root: Path, prices: PriceTable | None = None):
        self.root = Path(root)
        self.prices = prices or PriceTable()
        self._files: dict[Path, list] = {}   # path -> [offset, cost, n_records]

    def refresh(self):
        for f in self.root.rglob(JOURNAL):
            st = self._files.setdefault(f, [0, 0.0, 0])
            with open(f, "rb") as fh:
                fh.seek(st[0])
                chunk = fh.read()
            end = chunk.rfind(b"\n") + 1     # ignore a torn last line until it is complete
            for line in chunk[:end].splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                st[1] += self.record_cost(rec)
                st[2] += 1
            st[0] += end
        return self

    def record_cost(self, rec: dict) -> float:
        if not rec.get("input_tokens") and not rec.get("output_tokens") and not rec.get("billable_output_tokens"):
            return 0.0
        return self.prices.usage_cost(rec["requested_model"], rec)

    def by_group(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for f, (_, cost, _) in self._files.items():
            g = f.relative_to(self.root).parts[0]
            out[g] = out.get(g, 0.0) + cost
        return out

    @property
    def total(self) -> float:
        return sum(c for _, c, _ in self._files.values())


class Budget:
    """Caps for one Study 2 group. `caps` has the configs/caps.yaml layout; the group's check-group
    entry is `check_groups[f"study2_{group}"]` (stage study2) if present."""

    def __init__(self, *, root: Path, group: str, caps: dict, project_results: Path | None,
                 project_refresh_s: float = 60.0):
        self.journals = JournalLedger(root)
        self.group = group
        self.caps = caps
        self.project_results = project_results
        self.project_refresh_s = project_refresh_s
        self._project = (0.0, -1e9)

    def project_spend(self) -> float:
        """Live spend of all other stages (results/raw), refreshed at most every project_refresh_s."""
        if self.project_results is None:
            return 0.0
        value, at = self._project
        if time.monotonic() - at > self.project_refresh_s:
            value = Ledger(self.project_results, mode="live").total
            self._project = (value, time.monotonic())
        return value

    def check(self, reserve: float):
        self.journals.refresh()
        groups = self.journals.by_group()
        study2 = self.journals.total
        stage_cap = (self.caps.get("stages") or {}).get(STAGE)
        if stage_cap is None:
            raise Study2Stop(f"no cap configured for stage {STAGE!r} (fail closed)")
        g = (self.caps.get("check_groups") or {}).get(f"study2_{self.group}")
        if g is not None and groups.get(self.group, 0.0) + reserve > g["cap_usd"]:
            raise Study2Stop(f"group {self.group}: spent {groups.get(self.group, 0.0):.4f} + reserve "
                             f"{reserve:.4f} > cap {g['cap_usd']}")
        if study2 + reserve > stage_cap:
            raise Study2Stop(f"stage {STAGE}: spent {study2:.4f} + reserve {reserve:.4f} > cap {stage_cap}")
        total = study2 + self.project_spend()
        if total + reserve > self.caps["hard_cap_usd"]:
            raise Study2Stop(f"hard cap: spent {total:.4f} + reserve {reserve:.4f} > {self.caps['hard_cap_usd']}")
        return {"group": groups.get(self.group, 0.0), "study2": study2, "total": total}


def guarded_completion(backend, *, budget: Budget, reserve_usd: float, expected_model: str, stop_file: Path):
    stop_file = Path(stop_file)

    def completion(**kw):
        if stop_file.exists():
            raise Study2Stop(f"STOP file present: {stop_file}: {stop_file.read_text()[:300]}")
        budget.check(reserve_usd)
        response = backend(**kw)
        got = getattr(response, "model", None)
        if got != expected_model:
            stop_file.parent.mkdir(parents=True, exist_ok=True)
            with open(stop_file, "a") as fh:
                fh.write(f"response_model changed: expected {expected_model!r}, got {got!r}\n")
            raise Study2Stop(f"response_model {got!r} != {expected_model!r}")
        return response

    return completion
