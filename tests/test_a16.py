"""A16 (D39): byte identity to the Flash-Lite requests except the model, job list, order, exclusions, stop guard, and a
synthetic Holm-of-three with gatekeeping. No API call (mock backends only)."""
from __future__ import annotations

import collections
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.a16 import launch_a16 as L
from scripts.analysis import a16_addendum as A
from src.replay import a10, a16
from src.replay.request import canonical_json, messages_hash, mock_backend, run_verdict
from src.runner.costs import iter_call_lines

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
FL = "gemini/gemini-3.1-flash-lite"


@pytest.fixture(scope="module")
def fl_lines():
    return {r["call_id"]: r for r in iter_call_lines(RAW)
            if r.get("mode") == "live" and r.get("stage") in ("main", "a06", "a13", "a14")}


@pytest.fixture(scope="module")
def cells():
    shared = a16.shared_items()
    return [(o, v, ver) for o in a16.omission_items()
            for v, ver in sorted({(v, ver) for v, ver, _ in a16.item_cells(o["item_id"], shared)})]


# ------------------------------------------------------------------ byte identity

def test_messages_hash_equals_flash_lite_on_all_items(cells, fl_lines):
    """Every A16 cell's messages == the logged Flash-Lite messages of the same item, context and version (all draws)."""
    shared = a16.shared_items()
    n = 0
    for o, v, ver in cells:
        h = messages_hash(a16.build_messages(o, v, ver))
        ids = a16.flash_lite_call_ids(o["item_id"], v, ver, o["item_id"] in shared)
        for cid in ids:
            assert cid in fl_lines, cid
            assert fl_lines[cid]["messages_sha256"] == h, cid
            assert fl_lines[cid]["model"] == FL
            n += 1
    assert len(cells) == 50 * 8 + 22 and n == 2 * len(cells)


def _req(model, msgs):
    res = run_verdict(msgs, "record_extraction", mock_backend(), model=model, episode_id="t")
    assert len(res.requests) == 1
    return res.requests[0]


def test_request_identical_except_model_on_all_items(cells, fl_lines):
    """The 3.8-Flash request kwargs (unchanged upstream builder, with the D39 LiteLLM entry) equal the Flash-Lite
    request kwargs except `model`; messages byte-identical; equal to the saved Flash-Lite payload where that local
    file exists (results/requests/ is not committed)."""
    shared = a16.shared_items()
    saved = 0
    strip = lambda r: {k: x for k, x in r.items() if k != "model"}
    for o, v, ver in cells:
        msgs = a16.build_messages(o, v, ver)
        r38, rfl = _req(a16.MODEL_38_FLASH, msgs), _req(FL, msgs)
        assert r38["model"] == a16.MODEL_38_FLASH and rfl["model"] == FL
        assert set(r38) == set(rfl) and "allowed_openai_params" not in r38
        assert canonical_json(strip(r38)) == canonical_json(strip(rfl))
        assert canonical_json(r38["messages"]) == canonical_json(msgs)
        assert (r38["temperature"], r38["max_tokens"], r38["reasoning_effort"]) == (1.0, 64000, "high")
        assert r38["tool_choice"]["function"]["name"] == "submit_verdict"
        cid = a16.flash_lite_call_ids(o["item_id"], v, ver, o["item_id"] in shared)[0]
        rec = fl_lines[cid]
        p = ROOT / "results" / "requests" / rec["run_id"] / f"{rec['request_sha256'][0]}.json.gz"
        if p.exists():
            logged = json.loads(gzip.open(p, "rt").read())
            assert canonical_json(strip(logged)) == canonical_json(strip(r38)), cid
            saved += 1
    if saved == 0:
        pytest.skip("no saved Flash-Lite request payloads locally (results/requests/ is not committed)")


def test_litellm_entry_registered_fail_closed(monkeypatch):
    import litellm
    e = litellm.model_cost[a16.MODEL_38_FLASH]
    tpl = litellm.model_cost[a16.SAME_FAMILY_TEMPLATE]
    assert {k: v for k, v in e.items() if k.startswith("supports")} == \
        {k: v for k, v in tpl.items() if k.startswith("supports")}
    assert e["input_cost_per_token"] == pytest.approx(0.75e-6) and e["output_cost_per_token"] == pytest.approx(3.75e-6)
    assert a16.register_litellm_model() is not None   # idempotent
    bad = dict(e, supports_system_messages=False)
    monkeypatch.setitem(litellm.model_cost, a16.MODEL_38_FLASH, bad)
    with pytest.raises(a16.LiteLLMEntryMismatch):
        a16.register_litellm_model()


def _wire(model, msgs, monkeypatch):
    import litellm
    from litellm.llms.custom_httpx.http_handler import HTTPHandler
    got = {}

    class Captured(Exception):
        pass

    def post(self, url, data=None, json=None, **k):
        got["url"], got["body"] = url, (data if data is not None else json)
        raise Captured()
    monkeypatch.setattr(HTTPHandler, "post", post)
    with pytest.raises(Exception):
        litellm.completion(**{**_req(model, msgs), "num_retries": 0})
    b = got["body"]
    return got["url"], (json.loads(b) if isinstance(b, (str, bytes)) else b)


def test_wire_body_identical_except_model_on_all_cells(cells, monkeypatch):
    """LiteLLM's HTTP body for 3.8 Flash equals Flash-Lite's on every A16 cell (system_instruction, contents incl.
    thought signatures, tools, toolConfig, generationConfig with thinkingLevel high, temperature 1.0,
    max_output_tokens 64000); only the model name in the URL differs. Captured offline: the HTTP post is intercepted
    before any network access."""
    monkeypatch.setenv("GEMINI_API_KEY", "offline-test")
    for o, v, ver in cells:
        msgs = a16.build_messages(o, v, ver)
        u1, b1 = _wire(FL, msgs, monkeypatch)
        u2, b2 = _wire(a16.MODEL_38_FLASH, msgs, monkeypatch)
        assert "models/gemini-3.1-flash-lite:" in u1 and "models/gemini-3.8-flash:" in u2
        assert u1.replace("gemini-3.1-flash-lite", "M") == u2.replace("gemini-3.8-flash", "M")
        assert canonical_json(b1) == canonical_json(b2), (o["item_id"], v, ver)
        assert "system_instruction" in b2
        g = b2["generationConfig"]
        assert g["thinkingConfig"]["thinkingLevel"] == "high" and g["temperature"] == 1.0 \
            and g["max_output_tokens"] == 64000


# ------------------------------------------------------------------ job list and order

def test_job_list_counts_adjacency_seed():
    js = L.jobs("")
    ids = [j.call_id("a16") for j in js]
    assert len(js) == 822 and len(set(ids)) == 822
    assert all(i.startswith("a16:XVER:") for i in ids)
    assert all(j.model == "gemini/gemini-3.8-flash" for j in js)
    per = collections.Counter(j.item_id for j in js)
    shared = a16.shared_items()
    assert len(per) == 50 and len(shared) == 22
    assert all(n == (17 if i in shared else 16) for i, n in per.items())
    c = collections.Counter((j.variant, j.version) for j in js)
    assert c[("R1", "bait")] == 22 and all(n == 100 for k, n in c.items() if k != ("R1", "bait"))
    order = list(dict.fromkeys(j.item_id for j in js))
    first = {i: ids.index(next(x for x in ids if f":{i}:" in x)) for i in order}
    for i in order:   # item blocks adjacent
        k = [n for n, j in enumerate(js) if j.item_id == i]
        assert k == list(range(k[0], k[0] + len(k)))
    rng = np.random.default_rng(2026)
    om = a16.omission_items()
    assert order == [om[i]["item_id"] for i in rng.permutation(len(om))]
    assert sorted(first.values()) == list(first.values())


def test_parts_and_drops():
    js = L.jobs("")
    f3 = L.first_items(js)
    s0a, s0b, first = L.part_jobs("stage0a"), L.part_jobs("stage0b"), L.part_jobs("first")
    assert [(j.item_id, j.variant, j.version, j.draw) for j in s0a] == [(f3[0], "R4", "correct", 1)]
    assert len(s0b) == 9 and {(j.variant, j.version, j.draw) for j in s0b} == {
        ("R1", "omission", 1), ("R2", "omission", 1), ("R1+CHK", "omission", 1)}
    assert {j.item_id for j in s0b} == set(f3) and {j.item_id for j in first} == set(f3)
    ids_first = {j.call_id("a16") for j in first}
    assert {j.call_id("a16") for j in s0a + s0b} <= ids_first
    a = L.jobs("a")
    assert len(a) == 800 and not any(j.version == "bait" for j in a)
    ab = L.jobs("a,b")
    assert len(ab) == 700 and not any(j.variant == "R1+CHK" and j.draw == 2 for j in ab)
    abc = L.jobs("a,b,c")
    assert len(abc) == 400 and all(j.draw == 1 for j in abc)


# ------------------------------------------------------------------ stop guard

class _Resp:
    def __init__(self, model):
        self.model = model


def test_guard_400_stops(tmp_path):
    class BadRequestError(Exception):
        status_code = 400

    def backend(**kw):
        raise BadRequestError("INVALID_ARGUMENT: thought signature")
    g = a16.guard_backend(backend, "gemini-3.8-flash", call="c", d=tmp_path)
    with pytest.raises(a10.StopA10):
        g(model="x")
    assert a10.stop_file(tmp_path).exists()
    with pytest.raises(a10.StopA10):   # every later request refuses
        a16.guard_backend(lambda **k: _Resp("gemini-3.8-flash"), "gemini-3.8-flash", d=tmp_path)(model="x")


def test_guard_wrong_model_writes_stop_and_returns(tmp_path):
    g = a16.guard_backend(lambda **k: _Resp("gemini-3.8-flash"), "gemini-3.8-flash", d=tmp_path)
    assert g(model="x").model == "gemini-3.8-flash" and not a10.stop_file(tmp_path).exists()
    g2 = a16.guard_backend(lambda **k: _Resp("gemini-3.9-flash"), "gemini-3.8-flash", d=tmp_path)
    assert g2(model="x").model == "gemini-3.9-flash"
    assert "response model" in a10.stop_file(tmp_path).read_text()


def test_guard_spending_cap_and_other_errors(tmp_path):
    def cap(**kw):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: project spending cap reached")
    with pytest.raises(a10.StopA10):
        a16.guard_backend(cap, "gemini-3.8-flash", d=tmp_path)(model="x")
    d2 = tmp_path / "b"

    def boom(**kw):
        raise TimeoutError("timeout")
    with pytest.raises(TimeoutError):   # other errors go to upstream's retry logic
        a16.guard_backend(boom, "gemini-3.8-flash", d=d2)(model="x")
    assert not a10.stop_file(d2).exists()


# ------------------------------------------------------------------ exclusions

def test_d40_flagged_and_freeze(tmp_path, monkeypatch):
    flagged = A.d40_flagged(A.D40_SCAN)
    assert set(A.PRIMARY_EXCLUSIONS) == {"rep041_e06_alice", "rep044_e03_alice"} <= set(flagged)
    assert set(flagged) <= {o["item_id"] for o in a16.omission_items()}
    monkeypatch.setattr(A, "EXCLUSIONS", tmp_path / "ex.json")
    rec = A.freeze_exclusions()
    assert rec["excluded"] == sorted(A.PRIMARY_EXCLUSIONS) and rec["d40"]["flagged_items"] == flagged
    with pytest.raises(SystemExit):   # frozen once
        A.freeze_exclusions()
    monkeypatch.setattr(A, "EXCLUSIONS", tmp_path / "ex2.json")
    absent = ROOT / "data" / "derived" / "no_such_scan.csv"
    with pytest.raises(SystemExit):   # fail closed without a committed scan
        A.freeze_exclusions(absent)


def test_analyze_reads_nothing_before_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "EXCLUSIONS", tmp_path / "missing.json")

    def boom(*a, **k):
        raise AssertionError("A16 outcomes read before the exclusion freeze")
    monkeypatch.setattr(A, "load_stage", boom)
    assert A.analyze(pd.DataFrame(), pd.DataFrame())["status"] == "awaiting exclusion freeze"


# ------------------------------------------------------------------ synthetic Holm-of-three with gatekeeping

def _synthetic(p: dict, n_items=60, n_clusters=30, seed=1):
    """p[(variant, version)] = REJECT probability; 2 draws per cell."""
    rng = np.random.default_rng(seed)
    rows = []
    items = [f"s{i:03d}" for i in range(n_items)]
    for i in items:
        for (v, ver), pr in p.items():
            for d in (1, 2):
                rows.append(dict(call_id=f"{i}:{v}:{ver}:{d}", item_id=i, variant=v, version=ver, draw=d,
                                 y=float(rng.random() < pr), reasoning="", verdict_status="ok"))
    meta = pd.DataFrame({"item_id": items, "cluster": [f"c{k % n_clusters}" for k in range(n_items)]}).set_index("item_id")
    return pd.DataFrame(rows), meta


BASE_P = {("R1", "omission"): 0.5, ("R4", "omission"): 0.5, ("R2", "omission"): 0.5, ("R1+CHK", "omission"): 0.5,
          ("R0p", "correct"): 0.05, ("R4", "correct"): 0.05, ("R2", "correct"): 0.05, ("R1+CHK", "correct"): 0.05}


def test_holm_of_three_and_gatekeeping():
    p = dict(BASE_P)
    p[("R4", "omission")] = 1.0      # G large and positive
    p[("R1", "omission")] = 0.3
    p[("R2", "omission")] = 0.3      # H null
    p[("R1+CHK", "omission")] = 0.35  # C small
    calls, meta = _synthetic(p)
    out = A.primary(calls, meta)
    raw = {k: out[k]["p"] for k in ("G", "H", "C")}
    srt = sorted(raw, key=raw.get)
    exp, run = {}, 0.0
    for i, k in enumerate(srt):
        run = max(run, min(1.0, (3 - i) * raw[k]))
        exp[k] = run
    for k in raw:
        assert out[k]["p_holm"] == pytest.approx(exp[k])
        assert out[k]["significant"] == (exp[k] < 0.05)
    assert out["G"]["significant"] and out["D_G"]["tested"] and "p" in out["D_G"]
    assert not out["H"]["significant"] and out["D_H"]["tested"] is False and "p" not in out["D_H"]
    rows = A.interpretation(calls, meta, out)["rows"]
    assert rows["row1_G_significant_positive"] and not rows["row4_H_significant_positive"]
    assert not rows["row2_G_not_significant_and_R1om_ge_0p90"]


def test_interpretation_rows_2_and_5():
    p = dict(BASE_P)
    for v in ("R1", "R4", "R2"):
        p[(v, "omission")] = 0.97
    p[("R1+CHK", "omission")] = 0.97
    p[("R1+CHK", "correct")] = 0.05
    calls, meta = _synthetic(p, seed=3)
    out = A.primary(calls, meta)
    it = A.interpretation(calls, meta, out)
    assert not out["G"]["significant"]
    assert it["rows"]["row2_G_not_significant_and_R1om_ge_0p90"] == (it["detection_R1_om"] >= 0.90)
    assert it["rows"]["row5c_C_not_significant"]


def test_missing_sensitivities_and_verifier_comparison():
    calls, meta = _synthetic(BASE_P, seed=5)
    calls.loc[calls.index[:4], "y"] = np.nan
    a = A.primary(calls, meta, missing="accept")
    r = A.primary(calls, meta, missing="reject")
    assert a["G"]["n_items"] == r["G"]["n_items"] == 60
    fl, _ = _synthetic(BASE_P, seed=6)
    fl = fl[~((fl.variant == "R1") & (fl.version == "bait"))]
    vc = A.verifier_comparison(calls, fl, meta)
    assert set(vc["contrasts"]) == {"G", "H", "C"}
    d = vc["cells"]["R2|omission"]
    assert d["difference"]["estimate"] == pytest.approx(
        d["flash_38"]["estimate"] - d["flash_lite"]["estimate"], abs=1e-9)


def test_expected_model_per_mode(tmp_path, monkeypatch):
    """Mock mode expects the mock backend's model; without the launcher's setting the served model is required."""
    msgs = a16.build_messages(a16.omission_items()[0], "R4", "omission")
    monkeypatch.setenv("A10_GUARD_DIR", str(tmp_path / "g1"))
    monkeypatch.setenv(a16.EXPECT_ENV, "mock-model")
    a16.verdict_fn(a16.MODEL_38_FLASH)(msgs, "record_extraction", mock_backend(), model=a16.MODEL_38_FLASH)
    assert not a10.stop_file(tmp_path / "g1").exists()
    monkeypatch.delenv(a16.EXPECT_ENV)
    monkeypatch.setenv("A10_GUARD_DIR", str(tmp_path / "g2"))
    a16.verdict_fn(a16.MODEL_38_FLASH)(msgs, "record_extraction", mock_backend(), model=a16.MODEL_38_FLASH)
    assert "mock-model" in a10.stop_file(tmp_path / "g2").read_text()
