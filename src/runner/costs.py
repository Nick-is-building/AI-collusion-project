"""Price table, per-call cost from logged usage, and the spend ledger (fail-closed caps).

Cost of one API response (upstream usage record, experiments/usage.py):
    (input_tokens - cached_input_tokens) * input + cached_input_tokens * cached_input
    + billable_output_tokens * output
billable_output_tokens falls back to provider_output_tokens, then output_tokens + reasoning_tokens.
The tier is chosen by the record's input_tokens (Haiku: above 100k prompt tokens).
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"


class CapExceeded(RuntimeError):
    pass


class UnpricedModel(RuntimeError):
    pass


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIGS / name).read_text())


class PriceTable:
    def __init__(self, data: dict | None = None):
        self.models = (data or load_yaml("prices.yaml"))["models"]

    def documented(self, model: str) -> bool:
        return bool(self.models.get(model, {}).get("documented"))

    def tier(self, model: str, prompt_tokens: int) -> dict:
        if model not in self.models:
            raise UnpricedModel(f"no price entry for {model}")
        for t in self.models[model]["tiers"]:
            if t["max_prompt_tokens"] is None or prompt_tokens <= t["max_prompt_tokens"]:
                return t
        raise UnpricedModel(f"no tier for {model} at {prompt_tokens} tokens")

    def cost(self, model: str, input_tokens: int, cached: int = 0, output: int = 0) -> float:
        t = self.tier(model, input_tokens)
        unc = max(input_tokens - cached, 0)
        return (unc * t["input"] + cached * t["cached_input"] + output * t["output"]) / 1e6

    def usage_cost(self, model: str, usage: dict) -> float:
        inp = usage.get("input_tokens") or 0
        cached = usage.get("cached_input_tokens") or 0
        out = usage.get("billable_output_tokens")
        if out is None:
            out = usage.get("provider_output_tokens")
        if out is None:
            out = (usage.get("output_tokens") or 0) + (usage.get("reasoning_tokens") or 0)
        return self.cost(model, inp, cached, out)


def iter_call_lines(results_dir: Path):
    for f in sorted(Path(results_dir).glob("*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue  # a torn last line from a crash; the call is redone on resume
                if rec.get("type") == "call":
                    yield rec


class Ledger:
    """Spend from all logged calls in `results_dir` (all runs), split by mode and stage."""

    def __init__(self, results_dir: Path, mode: str):
        self.results_dir = Path(results_dir)
        self.mode = mode
        self.total = 0.0
        self.by_stage: dict[str, float] = {}
        self.by_check: dict[tuple[str, str], float] = {}
        for rec in iter_call_lines(self.results_dir):
            if rec.get("mode") == mode:
                self.add(rec.get("stage"), rec.get("cost_usd") or 0.0, check=rec.get("check"))

    def add(self, stage: str, cost: float, check: str | None = None):
        self.total += cost
        self.by_stage[stage] = self.by_stage.get(stage, 0.0) + cost
        if check is not None:
            self.by_check[(stage, check)] = self.by_check.get((stage, check), 0.0) + cost

    def group_spent(self, group: dict) -> float:
        return sum(self.by_check.get((group["stage"], c), 0.0) for c in group["checks"])

    def check(self, stage: str, projected: float, caps: dict, check: str | None = None):
        """Raise CapExceeded if spending `projected` more would exceed the stage cap, the hard cap, or
        the cap of a check group (caps["check_groups"]) that contains `check`."""
        for name, g in (caps.get("check_groups") or {}).items():
            if g["stage"] == stage and check in g["checks"]:
                spent = self.group_spent(g)
                if spent + projected > g["cap_usd"]:
                    raise CapExceeded(f"check group {name}: spent {spent:.4f} + projected {projected:.4f} > "
                                      f"cap {g['cap_usd']}")
        stage_cap = caps["stages"].get(stage)
        if stage_cap is None:
            raise CapExceeded(f"no cap configured for stage {stage!r}")
        if self.by_stage.get(stage, 0.0) + projected > stage_cap:
            raise CapExceeded(f"stage {stage}: spent {self.by_stage.get(stage, 0.0):.4f} + projected "
                              f"{projected:.4f} > cap {stage_cap}")
        if self.total + projected > caps["hard_cap_usd"]:
            raise CapExceeded(f"hard cap: spent {self.total:.4f} + projected {projected:.4f} > "
                              f"{caps['hard_cap_usd']}")
