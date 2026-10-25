"""A16 (D39): a second verifier on the identical D25 contexts, with the model as an argument.

Label (A16): "Gemini 3.8 Flash judging in Gemini 3.1 Flash-Lite's trajectories" (newer model of the same family; the
history was written by Flash-Lite). Never "in its own workflow".

Reusable wrapper (the A16 assignment asks for one so that a later session can reuse it for another model): every
function below takes the verifier model as an argument; contexts come only from the existing builders, called exactly
as the Flash-Lite stages called them (no new context code; src/replay/variants.py, r5.py, traces.py are not edited):

  cell (variant, version)   built as                                        Flash-Lite source of the same context
  R1      omission          variants.build(CUT, omission content)             a06:OMIT:<item>:R1:omission:<d>
  R4      omission          variants.build(R4, omission content)              a06:OMIT:<item>:R4:omission:<d>
  R2      omission/correct  variants.build(R2, omission content / None)       a13:LADDER:<item>:R2:<version>:<d>
  R1+CHK  omission/correct  a14.with_note_block(build(CUT, ...), "CHK")       a14:LOOK:<item>:CHK:<version>:<d>
  R0p     correct           variants.build(CUT, None)                         main:MAIN:<item>:R0p:correct:<d> (main-list
                                                                              items) or a06:OMIT:<item>:R0p:correct:<d>
  R4      correct           variants.build(R4, None)                          main:MAIN / a06:OMIT ...:R4:correct:<d>
  R1      bait (= R1-com)   variants.build(CUT, main-run commission bait)     main:MAIN:<item>:R1:bait:<d>
                            (only the 22 D25 items in the main list)

LiteLLM model entry: see `register_litellm_model` (D39 implementation choice, approved by Nick).
Request parameters are the main run's (src.replay.request.REQUEST_PARAMS: temperature 1.0, reasoning_effort "high",
max output 64,000; forced submit_verdict; upstream's 3 verdict attempts), through the unchanged upstream builder.

Stop guard (`guarded_verdict`): the A10 guard (src.replay.a10.guard_backend: STOP on any 429 containing "spending cap";
STOP at more than 10 quota 429s within 5 minutes; STOP file checked before every request) plus two A16 rules:
  - any HTTP 400 (status_code 400, BadRequestError, or "INVALID_ARGUMENT" in the text): STOP file, StopA10 is raised
    (A16 stage 0: "any 400 on a signature or malformed history stops A16"; no signature stripping, no retry);
  - any API response whose model (provider prefix stripped) differs from the expected served model: STOP file is
    written and the response is returned, so the call is logged; every worker stops at its next request.
The guard directory is $A10_GUARD_DIR (the launcher sets logs/a16_guard/<mode>/).
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path

from src.replay import a10, a14
from src.replay.request import run_verdict
from src.replay.variants import build, load_item
from src.runner.estimates import input_tokens
from src.runner.costs import PriceTable
from src.runner.item_lists import load_bait, main_items
from src.runner.runner import Job, normalize_model

ROOT = Path(__file__).resolve().parents[2]
OMISSION_DIR = ROOT / "data" / "derived" / "omission_baits"
MODEL_38_FLASH = "gemini/gemini-3.8-flash"
LABEL_38_FLASH = "Gemini 3.8 Flash judging in Gemini 3.1 Flash-Lite's trajectories"

# ------------------------------------------------------------------ LiteLLM model entry (D39, Nick-approved)
# LiteLLM 1.94.1's bundled model map (pinned: src/upstream.py sets LITELLM_LOCAL_MODEL_COST_MAP) has no
# gemini/gemini-3.8-flash entry. Without one, LiteLLM sends the system prompt as text in the first user turn instead of
# Gemini's system_instruction, and upstream adds allowed_openai_params=["reasoning_effort"]. `register_litellm_model`
# adds an in-process entry whose capability flags are copied from the bundled Flash-Lite entry and whose prices are
# the pricing page's (configs/prices.yaml); upstream code is untouched. Then the HTTP body equals Flash-Lite's except
# the model name (tests/test_a16.py). Fail closed: an existing entry with different capability flags raises.
SAME_FAMILY_TEMPLATE = "gemini/gemini-3.1-flash-lite"


class LiteLLMEntryMismatch(RuntimeError):
    pass


def litellm_entry(model: str) -> dict:
    import litellm
    tpl = litellm.model_cost[SAME_FAMILY_TEMPLATE]
    entry = {k: v for k, v in tpl.items() if "cost" not in k}
    t = PriceTable().tier(model, 0)   # configs/prices.yaml (pricing page); fails closed without an entry
    entry.update(input_cost_per_token=t["input"] / 1e6, output_cost_per_token=t["output"] / 1e6,
                 output_cost_per_reasoning_token=t["output"] / 1e6, cache_read_input_token_cost=t["cached_input"] / 1e6)
    return entry


def register_litellm_model(model: str = MODEL_38_FLASH) -> dict:
    import src.upstream  # noqa: F401  (pins the bundled cost map before litellm is imported)
    import litellm
    want = litellm_entry(model)
    have = litellm.model_cost.get(model)
    if have is not None:
        caps = {k for k in set(want) | set(have) if k.startswith("supports")}
        diff = sorted(k for k in caps if bool(want.get(k)) != bool(have.get(k)))
        if diff:
            raise LiteLLMEntryMismatch(f"existing LiteLLM entry for {model} differs in {diff}")
        return have
    litellm.register_model({model: want})
    return want


register_litellm_model()   # at import: the launcher's workers import this module through the job factory

OM_VARIANTS = ("R1", "R4", "R2", "R1+CHK")
COR_VARIANTS = ("R0p", "R4", "R2", "R1+CHK")
COM_CELL = ("R1", "bait")
BASE = {"R1": "CUT", "R0p": "CUT", "R4": "R4", "R2": "R2", "R1+CHK": "CUT"}


def omission_items() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(OMISSION_DIR.glob("rep*_alice.json"))]


def shared_items() -> set[str]:
    """D25 items that also have a main-run commission bait (main list)."""
    om = {o["item_id"] for o in omission_items()}
    return om & set(main_items().item_id)


def bob_content(o: dict, version: str):
    if version == "omission":
        return o["bob_r1_content"]
    if version == "correct":
        return None   # Bob's original round-1 message
    if version == "bait":
        return load_bait(o["item_id"])["bob_r1_content"]
    raise ValueError(version)


def build_messages(o: dict, variant: str, version: str) -> list:
    """The cell's context, built exactly as the Flash-Lite stage built it (see the table above)."""
    if (variant, version) == COM_CELL or (version == "omission" and variant in OM_VARIANTS) \
            or (version == "correct" and variant in COR_VARIANTS):
        msgs = build(load_item(o["trace"], int(o["ep_index"])), BASE[variant], bob_r1_content=bob_content(o, version))
        return a14.with_note_block(msgs, "CHK") if variant == "R1+CHK" else msgs
    raise ValueError(f"no A16 cell {variant} {version}")


def flash_lite_call_ids(item_id: str, variant: str, version: str, in_main: bool) -> list[str]:
    """Call IDs of the existing Flash-Lite calls with the same item, context and version (all draws)."""
    if (variant, version) == COM_CELL:
        return [f"main:MAIN:{item_id}:R1:bait:{d}" for d in (1, 2)]
    if variant == "R2":
        return [f"a13:LADDER:{item_id}:R2:{version}:{d}" for d in (1, 2)]
    if variant == "R1+CHK":
        return [f"a14:LOOK:{item_id}:CHK:{version}:{d}" for d in (1, 2)]
    if version == "omission" and variant in ("R1", "R4"):
        return [f"a06:OMIT:{item_id}:{variant}:omission:{d}" for d in (1, 2)]
    if version == "correct" and variant in ("R0p", "R4"):
        pre = "main:MAIN" if in_main else "a06:OMIT"
        return [f"{pre}:{item_id}:{variant}:correct:{d}" for d in (1, 2)]
    raise ValueError(f"no A16 cell {variant} {version}")


def flash_lite_cell(variant: str, version: str) -> tuple[str, str]:
    """(variant, version) label of the Flash-Lite cell in the analysis frames."""
    return ("CHK", version) if variant == "R1+CHK" else (variant, version)


# ------------------------------------------------------------------ stop guard

def is_400(exc: BaseException) -> bool:
    t = str(exc)
    return (getattr(exc, "status_code", None) == 400 or type(exc).__name__ == "BadRequestError"
            or "INVALID_ARGUMENT" in t)


def guard_backend(backend, served: str, call: str = "", d: Path | None = None):
    d = d or a10.guard_dir()
    inner = a10.guard_backend(backend, call=call, d=d)

    def guarded(**kwargs):
        try:
            resp = inner(**kwargs)
        except a10.StopA10:
            raise
        except Exception as exc:
            if is_400(exc):
                a10._write_stop(d, "HTTP 400 (A16: no signature stripping, no retry)", call, str(exc))
                raise a10.StopA10(f"HTTP 400: {str(exc)[:300]}") from exc
            raise
        got = normalize_model(str(getattr(resp, "model", "") or ""))
        if got != served:
            a10._write_stop(d, f"response model {got!r} != {served!r}", call, "")
        return resp
    return guarded


EXPECT_ENV = "A16_EXPECT_MODEL"   # set by the launcher: the served model in live mode, "mock-model" in mock mode


def guarded_verdict(messages, task_type, backend, *, served: str, **kw):
    served = os.environ.get(EXPECT_ENV) or served
    return run_verdict(messages, task_type, guard_backend(backend, served, call=kw.get("episode_id", "")), **kw)


def verdict_fn(model: str):
    return functools.partial(guarded_verdict, served=normalize_model(model))


# ------------------------------------------------------------------ jobs

def make_job(o: dict, variant: str, version: str, draw: int, *, model: str, check: str = "XVER",
             fn=None) -> Job:
    """One verdict job on an A16 cell for `model` (fn: verdict function; default: run_verdict behind the A16 guard)."""
    item = o["item_id"]
    if not ((variant, version) == COM_CELL or (version == "omission" and variant in OM_VARIANTS)
            or (version == "correct" and variant in COR_VARIANTS)):
        raise ValueError(f"no A16 cell {variant} {version}")
    return Job(check=check, item_id=item, variant=variant, version=version, draw=draw, judge="alice",
               task_type="record_extraction", build_messages=lambda: build_messages(o, variant, version),
               est_input_tokens=input_tokens(item, BASE[variant]), model=model,
               verdict_fn=fn or verdict_fn(model))


def item_cells(item_id: str, shared: set[str], draws: int = 2) -> list[tuple[str, str, int]]:
    cells = [(v, "omission", d) for v in OM_VARIANTS for d in range(1, draws + 1)]
    cells += [(v, "correct", d) for v in COR_VARIANTS for d in range(1, draws + 1)]
    if item_id in shared:
        cells.append((*COM_CELL, 1))
    return cells
