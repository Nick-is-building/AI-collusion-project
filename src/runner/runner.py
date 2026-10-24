"""Resumable, append-only verdict-call runner (CLAUDE.md "Resilience"; PROJECT_PLAN.md 13, 23.2).

- One run ID per launch; output `<results_dir>/<run_id>.jsonl`, one JSON line per completed call,
  written, flushed and fsynced immediately. A `run_start` line records provenance; a `run_end`
  line records why the run stopped.
- `call_id` = "stage:check:item:variant:version:draw" (deterministic). On launch, every call_id
  already logged in any `*.jsonl` of the same results dir with the same stage and mode is skipped,
  so a restart continues and never duplicates; runs are never mixed into one file.
- Each call goes through `src.replay.request.run_verdict` (Shi et al.'s verdict code path). API
  retries: upstream `experiments.agents.LLM_MAX_RETRIES` (20) is overridden to `api_max_retries`
  from configs/models.yaml (5, plan section 13) for the duration of the run.
- Cost: from the logged upstream usage records x configs/prices.yaml. Fail closed: before each
  call, `Ledger.check` with a conservative pre-check cost against the stage cap, the hard cap, and
  any `check_groups` cap in configs/caps.yaml that lists the job's check; a call to a model without a documented
  price is refused unless `allow_undocumented_price` is set for that job.
- `response_model`: the first value observed for a requested model (in earlier runs of this
  results dir, or in this run) is the reference; any change stops the run after logging the call.
- Missing: an exception after upstream retries -> status "missing" (verdict_status
  "missing_error"); no verdict after the 3 verdict attempts -> upstream forced reject, logged with
  forced=True and verdict_status "missing_forced" (plan 13: recorded as missing).
- API errors: upstream records one usage record per failed attempt with `error_category`; the
  call line carries `api_error_counts` and `n_rate_limit` (429: transient_rate_limit + hard_quota),
  also for calls that end in an exception.
- Full request kwargs are saved gzipped under `requests_dir/<run_id>/` (local; reconstructable);
  their SHA-256 is in the JSONL line.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import gzip
import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import src.upstream  # noqa: F401
import experiments.agents as up_agents
import litellm

from src.replay.request import canonical_json, messages_hash, request_hash, run_verdict
from src.runner.costs import CapExceeded, Ledger, PriceTable, UnpricedModel, iter_call_lines, load_yaml
from src.runner.estimates import precheck_cost

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_COMMIT = src.upstream.UPSTREAM_COMMIT


class ModelChanged(RuntimeError):
    pass


class LiveNotAuthorized(RuntimeError):
    pass


@dataclass
class Job:
    check: str
    item_id: str
    variant: str
    version: str              # "correct" | "bait"
    draw: int
    judge: str
    task_type: str
    build_messages: Callable[[], list]   # lazily built message list
    est_input_tokens: int
    model: str = "gemini/gemini-3.1-flash-lite"
    allow_undocumented_price: bool = False
    meta: dict = field(default_factory=dict)
    # optional replacement for run_verdict with the same signature (R6 gate: src.replay.r6.run_r6
    # bound to the item's transmitted log); its VerdictResult.extra is logged as `extra`
    verdict_fn: Callable | None = None

    def call_id(self, stage: str) -> str:
        return f"{stage}:{self.check}:{self.item_id}:{self.variant}:{self.version}:{self.draw}"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def git_state() -> tuple[str, bool]:
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
                                    capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return "unknown", True
    return head, dirty


@contextlib.contextmanager
def upstream_max_retries(n: int):
    old = up_agents.LLM_MAX_RETRIES
    up_agents.LLM_MAX_RETRIES = n
    try:
        yield
    finally:
        up_agents.LLM_MAX_RETRIES = old


def live_backend():
    """Thin wrapper around litellm.completion. Only reachable through Runner(mode='live')."""
    def backend(**kwargs):
        return litellm.completion(**kwargs)
    return backend


def assert_live_allowed(stage: str, approved_stage: str | None):
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise LiveNotAuthorized("live mode is disabled under pytest")
    if approved_stage != stage:
        raise LiveNotAuthorized(f"live mode needs --approved-stage {stage} (got {approved_stage!r})")
    head, dirty = git_state()
    if dirty or head == "unknown":
        raise LiveNotAuthorized("live mode needs a clean, committed working tree (provenance)")


class Runner:
    def __init__(self, *, stage: str, mode: str, results_dir: Path, requests_dir: Path, backend=None,
                 approved_stage: str | None = None, seed: int | None = None, caps: dict | None = None,
                 prices: PriceTable | None = None, max_retries: int | None = None, log=print):
        if mode not in ("mock", "live"):
            raise ValueError(mode)
        if mode == "live":
            assert_live_allowed(stage, approved_stage)
            backend = live_backend()
        elif backend is None:
            raise ValueError("mock mode needs a mock backend")
        self.stage, self.mode, self.backend, self.seed, self.log = stage, mode, backend, seed, log
        self.results_dir, self.requests_dir = Path(results_dir), Path(requests_dir)
        self.caps = caps or load_yaml("caps.yaml")
        self.prices = prices or PriceTable()
        self.max_retries = max_retries if max_retries is not None else load_yaml("models.yaml")["api_max_retries"]
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = f"{stage}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
        self.path = self.results_dir / f"{self.run_id}.jsonl"
        self.done: set[str] = set()
        self.ref_model: dict[str, str] = {}
        for rec in iter_call_lines(self.results_dir):
            if rec.get("mode") != mode:
                continue
            if rec.get("stage") == stage:
                self.done.add(rec["call_id"])
            for m in rec.get("response_models") or []:
                self.ref_model.setdefault(rec["model"], m)
        self.ledger = Ledger(self.results_dir, mode)
        head, dirty = git_state()
        self.provenance = dict(run_id=self.run_id, stage=stage, mode=mode, git_commit=head, git_dirty=dirty,
                               litellm_version=getattr(litellm, "__version__", None) or _pkg_version("litellm"),
                               upstream_commit=UPSTREAM_COMMIT, seed=seed, api_max_retries=self.max_retries)

    def _write(self, rec: dict):
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def run(self, jobs: list[Job]) -> dict:
        todo = [j for j in jobs if j.call_id(self.stage) not in self.done]
        self.log(f"[{self.run_id}] {len(jobs)} jobs, {len(jobs) - len(todo)} already done, {len(todo)} to run")
        self._write(dict(type="run_start", ts_utc=utc_now(), n_jobs=len(jobs), n_todo=len(todo), **self.provenance))
        stats = dict(completed=0, missing=0, cost_usd=0.0, stopped=None)
        try:
            with upstream_max_retries(self.max_retries):
                for job in todo:
                    self._one(job, stats)
        except (CapExceeded, ModelChanged, UnpricedModel) as exc:
            stats["stopped"] = f"{type(exc).__name__}: {exc}"
            self.log(f"[{self.run_id}] STOP {stats['stopped']}")
        self._write(dict(type="run_end", ts_utc=utc_now(), run_id=self.run_id, **stats))
        return stats

    def _one(self, job: Job, stats: dict):
        cid = job.call_id(self.stage)
        if not self.prices.documented(job.model) and not job.allow_undocumented_price:
            raise UnpricedModel(f"{job.model} has no documented price; refused (fail closed)")
        pre = precheck_cost(self.prices, job.model, job.est_input_tokens)
        self.ledger.check(self.stage, pre, self.caps, check=job.check)
        msgs = job.build_messages()
        t0 = utc_now()
        status, err, res = "complete", None, None
        exc_usage, exc_requests = [], []
        try:
            fn = job.verdict_fn or run_verdict
            res = fn(msgs, job.task_type, self.backend, judge=job.judge, model=job.model, episode_id=cid)
        except Exception as exc:  # after upstream retries (LLMRetryLimitExceededError, 4xx, ...)
            status, err = "missing", f"{type(exc).__name__}: {str(exc)[:1000]}"
            exc_usage, exc_requests = getattr(exc, "replay_usage", []), getattr(exc, "replay_requests", [])
        usage = res.usage if res else exc_usage
        requests = res.requests if res else exc_requests
        cost = sum(self.prices.usage_cost(job.model, u) for u in usage)
        models = sorted({u.get("response_model") for u in usage if u.get("response_model")})
        error_counts = error_category_counts(usage)
        req_hashes = [request_hash(r) for r in requests]
        if requests:
            d = self.requests_dir / self.run_id
            d.mkdir(parents=True, exist_ok=True)
            for h, r in zip(req_hashes, requests):
                with gzip.open(d / f"{h}.json.gz", "wt", encoding="utf-8") as fh:
                    fh.write(canonical_json(r))
        if res is None:
            vstatus = "missing_error"
        elif res.forced:
            vstatus = "missing_forced"
        else:
            vstatus = "ok"
        rec = dict(type="call", call_id=cid, run_id=self.run_id, stage=self.stage, mode=self.mode,
                   check=job.check, item_id=job.item_id, variant=job.variant, version=job.version, draw=job.draw,
                   judge=job.judge, task_type=job.task_type, model=job.model, seed=self.seed,
                   git_commit=self.provenance["git_commit"], litellm_version=self.provenance["litellm_version"],
                   upstream_commit=UPSTREAM_COMMIT, ts_start_utc=t0, ts_end_utc=utc_now(),
                   messages_sha256=messages_hash(msgs), request_sha256=req_hashes, n_api_requests=len(req_hashes),
                   status=status, verdict_status=vstatus, error=err,
                   verdict=res.verdict if res else None, reasoning=res.reasoning if res else None,
                   forced=res.forced if res else None, response_models=models, usage=usage,
                   api_error_counts=error_counts, n_rate_limit=n_rate_limit(error_counts),
                   cost_usd=cost, est_input_tokens=job.est_input_tokens,
                   response_messages=res.messages_after[len(msgs):] if res else None, meta=job.meta,
                   extra=res.extra if res else None)
        self._write(rec)
        self.ledger.add(self.stage, cost, check=job.check)
        stats["cost_usd"] += cost
        stats["completed" if status == "complete" else "missing"] += 1
        ref = self.ref_model.get(job.model)
        for m in models:
            if ref is None:
                self.ref_model[job.model] = ref = m
            elif m != ref:
                raise ModelChanged(f"{job.model}: response_model {m!r} != first observed {ref!r} (call {cid})")


RATE_LIMIT_CATEGORIES = ("transient_rate_limit", "hard_quota")  # upstream _classify_llm_error (HTTP 429)


def error_category_counts(usage: list) -> dict:
    """Upstream error records per category (one record per failed API attempt)."""
    out: dict[str, int] = {}
    for u in usage:
        c = u.get("error_category")
        if c:
            out[c] = out.get(c, 0) + 1
    return out


def n_rate_limit(counts: dict) -> int:
    return sum(counts.get(c, 0) for c in RATE_LIMIT_CATEGORIES)


def _pkg_version(name):
    from importlib.metadata import version
    return version(name)
