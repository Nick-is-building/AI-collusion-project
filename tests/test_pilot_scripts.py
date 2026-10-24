"""Pilot check scripts run end to end in mock mode (no network); output only under scratch/."""
import json
import shutil
import uuid
from pathlib import Path

import pytest

import scripts.pilot.common as common
from scripts.pilot import (p1_model_route, p2_r0_identity, p3_edited_histories, p9_fidelity_mini, p10_cost,
                           p11_effect_check)
from src.runner.runner import LiveNotAuthorized

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sdir():
    d = ROOT / "scratch" / "pytest" / f"pilot-{uuid.uuid4().hex[:8]}"
    d.mkdir(parents=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def args(sdir, *extra):
    return ["--results-dir", str(sdir / "raw"), "--requests-dir", str(sdir / "req"), *extra]


def calls(sdir):
    return [json.loads(l) for f in (sdir / "raw").glob("*.jsonl") for l in f.read_text().splitlines()
            if json.loads(l)["type"] == "call"]


def test_plan_only_makes_no_calls(sdir):
    assert p2_r0_identity.main(args(sdir, "--plan")) is None
    assert not (sdir / "raw").exists()


@pytest.mark.parametrize("mod,n", [(p1_model_route, 1), (p2_r0_identity, 10), (p3_edited_histories, 15),
                                   (p9_fidelity_mini, 40)])
def test_mock_end_to_end(sdir, mod, n):
    st = mod.main(args(sdir))
    assert st["completed"] == n and st["missing"] == 0 and st["stopped"] is None
    cs = calls(sdir)
    assert len(cs) == n and all(c["mode"] == "mock" and c["verdict_status"] == "ok" for c in cs)
    assert len({c["call_id"] for c in cs}) == n
    # rerun resumes: nothing left to do
    assert mod.main(args(sdir))["completed"] == 0


def test_item_choice_from_holdout_and_fidelity():
    h = set(common.holdout().item_id)
    assert set(p2_r0_identity.items().item_id) <= h and len(p2_r0_identity.items()) == 10
    assert set(p3_edited_histories.items().item_id) <= h and len(p3_edited_histories.items()) == 5
    f = p9_fidelity_mini.items()
    assert (f.role == "original_reject").sum() == 8 and (f.role == "matched_accept").sum() == 12
    assert list(p2_r0_identity.items().item_id) == list(p2_r0_identity.items().item_id)  # seeded


def test_p1_with_37(sdir):
    st = p1_model_route.main(args(sdir, "--allow-37"))
    assert st["completed"] == 2
    assert {c["model"] for c in calls(sdir)} == {"gemini/gemini-3.1-flash-lite", "gemini/gemini-3.7-flash"}


def test_p11_blocked_then_with_baits(sdir, monkeypatch):
    monkeypatch.setattr(common, "BAITS", sdir / "baits")
    assert p11_effect_check.main(args(sdir)) is None
    (sdir / "baits").mkdir()
    rows = common.holdout().head(2)
    for r in rows.itertuples():
        from src.replay.variants import load_item
        ctx = load_item(r.trace, r.ep_index)
        (sdir / "baits" / f"{r.item_id}.json").write_text(
            json.dumps({"bob_r1_content": ctx.messages[ctx.cut_idx]["content"] + " BAIT"}))
    st = p11_effect_check.main(args(sdir))
    assert st["completed"] == 4
    cs = calls(sdir)
    assert all(c["version"] == "bait" for c in cs) and {c["variant"] for c in cs} == {"R1", "R4"}


def test_p10_measured_and_projection(sdir, capsys):
    p2_r0_identity.main(args(sdir))
    out = p10_cost.main(["--results-dir", str(sdir / "raw")])
    assert out["total"] < 250 and out["n_main"] <= 148
    assert "P2" in capsys.readouterr().out


def test_live_refused_from_cli(sdir):
    with pytest.raises(LiveNotAuthorized):
        p2_r0_identity.main(args(sdir, "--live", "--approved-stage", "pilot"))
    with pytest.raises(LiveNotAuthorized):
        p2_r0_identity.main(args(sdir, "--live"))
