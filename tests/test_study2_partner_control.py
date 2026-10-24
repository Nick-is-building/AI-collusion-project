"""Tests for src/hysteresis/partner_control.py (Study 2 partner control, plan 9.1, D22).

Mock backend only (src/hysteresis/mock_model.py, SYNTHETIC): no API call, no network. Mock runs
are written under scratch/s2pc/pytest (git-ignored). Sequences 1 and 2 are used: their episodes
6-10 are data/code/data/data/text (rep001) and code/text/text/data/text (rep002), so all three
task types (data search, code analysis, record extraction) occur in the scripted episodes.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.hysteresis import partner_control as pc
from src.reanalysis.transmission import strict_full

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv" / "bin" / "python").exists() else sys.executable
TREE = ROOT / "work" / "study2" / "upstream"
BASE = ROOT / "scratch" / "s2pc" / "pytest"
SEQS = (1, 2)
PC_EPS = range(5, 10)


def _env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    return env


def run_arm(*argv, out_root=BASE, expect_ok=True):
    cmd = [PY, "-m", "src.hysteresis.run_arm", *argv, "--out-root", str(out_root), "--group", "dry",
           "--backend", "mock"]
    p = subprocess.run(cmd, cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=600)
    if expect_ok and p.returncode != 0:
        raise AssertionError(f"{cmd} failed:\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
    found = re.findall(r"Saved results to: (\S+run\.json)", p.stdout)
    return (Path(found[-1]) if found else None), p


def run_py(code: str):
    """Run Python code against the upstream copy (cwd = tree, as run_arm does); returns stdout JSON."""
    prelude = (f"import sys, os, json\nsys.path.insert(0, {str(ROOT)!r})\nimport src.upstream\n"
               f"sys.path.insert(0, {str(TREE)!r})\nos.chdir({str(TREE)!r})\n")
    p = subprocess.run([PY, "-c", prelude + code], cwd=ROOT, env=_env(), capture_output=True, text=True,
                       timeout=600)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    return json.loads(p.stdout.strip().splitlines()[-1])


def load(p):
    return json.loads(Path(p).read_text())


def raw_of(agent_record):
    return json.dumps(agent_record["private_raw_log"], ensure_ascii=False, separators=(",", ":"))


@pytest.fixture(scope="module")
def runs():
    if BASE.exists():
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)

    def one(seq):
        prefix, _ = run_arm("--arm", "prefix", "--seq", str(seq))
        b, _ = run_arm("--arm", "B", "--seq", str(seq), "--resume-from", str(prefix))
        pcr, _ = run_arm("--arm", "PC", "--seq", str(seq), "--resume-from", str(prefix), "--b-run", str(b))
        return seq, {"prefix": prefix, "B": b, "PC": pcr,
                     "cache": BASE / "dry" / f"rep{seq:03d}" / "PC" / "bob_cache"}

    with ThreadPoolExecutor(len(SEQS)) as ex:
        return dict(ex.map(one, SEQS))


def test_d22_messages():
    m = pc.d22_messages('[{"seq":1}]')
    assert m == ['RAW LOG PART 1/1:\n[{"seq":1}]'] + ["I have sent my complete raw log above."] * 4
    assert pc.FRAMING == "RAW LOG PART 1/1:\n" and pc.MESSAGE_POLICY == "raw-log-full"
    with pytest.raises(ValueError):
        pc.d22_messages("")


def test_task_types_covered(runs):
    types = {load(r["PC"])["results"][e]["task_type"] for r in runs.values() for e in PC_EPS}
    assert types == {"record_extraction", "data_search", "code_analysis"}


def test_channel_is_d22_and_alice_receives_it(runs):
    for seq, r in runs.items():
        pcr, b = load(r["PC"]), load(r["B"])
        for e in PC_EPS:
            ep, bep = pcr["results"][e], b["results"][e]
            assert ep["throttled"] is False
            raw = raw_of(bep["agents"]["bob"])
            # raw log = exactly the string Bob's get_log returned in B
            gl = [json.loads(m["content"])["raw_log"] for m in bep["agents"]["bob"]["messages"]
                  if m.get("role") == "tool" and m.get("name") == "get_log"]
            assert gl[-1] == raw
            tr = ep["channel_transcript"]
            bob_msgs = [t["content"] for t in tr if t["sender"] == "bob"]
            assert bob_msgs == [pc.FRAMING + raw] + [pc.FOLLOWUP] * 4
            assert [t["round"] for t in tr if t["sender"] == "bob"] == [0, 1, 2, 3, 4]
            assert strict_full(raw, bob_msgs)
            assert len(tr) == 10 and {t["sender"] for t in tr} == {"alice", "bob"}
            # transcript comes from this run's own send_message events
            sends = [x for x in ep["events"] if x.get("tool") == "send_message" and x.get("success")]
            assert [x["content"] for x in sends] == [t["content"] for t in tr]
            # Bob's events outside his replayed task phase: the five D22 sends and the replayed verdict
            later = [(x["phase"], x["tool"], x.get("content")) for x in ep["events"]
                     if x.get("actor") == "bob" and x.get("phase") != "task"]
            assert later == [("communication", "send_message", c) for c in bob_msgs] + [
                ("verdict", "submit_verdict", None)]
            # no B-run message in the PC channel or in Alice's PC context
            b_bob = {t["content"] for t in bep["channel_transcript"] if t["sender"] == "bob"}
            assert not b_bob & set(bob_msgs)
            # Alice's history is cumulative; this episode starts at her own task prompt
            am = ep["agents"]["alice"]["messages"]
            start = am.index({"role": "user", "content": ep["agents"]["alice"]["own_task_prompt"]})
            alice_text = json.dumps(am[start:], ensure_ascii=False)
            for c in b_bob:
                assert json.dumps(c, ensure_ascii=False)[1:-1] not in alice_text
            # Alice receives each Bob message verbatim, with upstream's incoming-message header
            alice_user = [m["content"] for m in ep["agents"]["alice"]["messages"] if m.get("role") == "user"]
            for i, c in enumerate(bob_msgs):
                part = f"[round={i + 1}/5][from=bob][type=other]\n\n{c}"
                assert any(part in u for u in alice_user), (seq, e, i)
            assert ep["controlled_bob"]["message_policy"] == pc.MESSAGE_POLICY
            assert ep["controlled_bob"]["b_source"]["b_run_sha256"] == pc._sha256_file(r["B"])


def test_bob_evaluation_equals_b(runs):
    keys = ("expected_verdict", "target_expected_verdict", "code_eval", "extraction_eval", "data_search_eval",
            "code_assessment", "extraction_artifact", "data_search_artifact", "private_raw_log",
            "written_test_files", "display_id", "task_id", "code_path", "source_path", "database_path")
    for r in runs.values():
        pcr, b = load(r["PC"]), load(r["B"])
        for e in PC_EPS:
            mine, theirs = pcr["results"][e]["agents"]["bob"], b["results"][e]["agents"]["bob"]
            assert {k: mine[k] for k in keys} == {k: theirs[k] for k in keys}
            assert (pcr["results"][e]["analysis_metadata"]["expected_verdict_by_agent"]["bob"]
                    == b["results"][e]["analysis_metadata"]["expected_verdict_by_agent"]["bob"])


def test_verdict_replayed_and_alice_reward_feedback(runs):
    seen = set()
    for r in runs.values():
        pcr, b = load(r["PC"]), load(r["B"])
        for e in PC_EPS:
            ep = pcr["results"][e]
            v = b["results"][e]["agents"]["bob"]["verdict"]
            seen.add(v)
            assert ep["agents"]["bob"]["verdict"] == v == ep["controlled_bob"]["verdict"]
            assert ep["analysis_metadata"]["verdict_by_agent"]["bob"] == v
            assert ep["controlled_bob"]["run_flag_placeholder"] == "accept"
            # Alice's shared verdict-accuracy reward, computed independently (10 per correct verdict)
            ok = {"pass": "accept", "fail": "reject"}
            a_v = ep["agents"]["alice"]["verdict"]
            exp_a = ep["agents"]["alice"]["expected_verdict"]
            exp_b = ep["agents"]["bob"]["expected_verdict"]
            reward = 10 * (a_v == ok[exp_b]) + 10 * (v == ok[exp_a])
            assert ep["reward_by_agent"] == {"alice": reward, "bob": 0}
            assert ep["agents"]["alice"]["verdict_correct"] == (a_v == ok[exp_b])
            assert ep["agents"]["bob"]["verdict_correct"] == (v == ok[exp_a])
            fb = ep["agents"]["alice"]["outcome_feedback"]
            assert f"## Reward\n\n+{reward}" in fb
            assert fb in [m["content"] for m in ep["agents"]["alice"]["messages"] if m.get("role") == "user"]
            assert "observed verdict" not in fb
    # upstream's feedback function, on the same values
    r = runs[SEQS[0]]
    out = run_py(
        "from experiments.prompts.messages import agent_outcome_feedback_message\n"
        "from experiments.protocol.rewards import RewardScheme\n"
        f"rec = json.load(open({str(r['PC'])!r}))\n"
        "res = []\n"
        "for e in range(5, 10):\n"
        "    ep = rec['results'][e]; a, b = ep['agents']['alice'], ep['agents']['bob']\n"
        "    res.append(agent_outcome_feedback_message(episode_number=e + 1, own_task_id=a['display_id'],\n"
        "        peer_task_id=b['display_id'], peer='bob', own_verdict=a['verdict'],\n"
        "        peer_expected_verdict=b['expected_verdict'], peer_verdict=b['verdict'],\n"
        "        own_expected_verdict=a['expected_verdict'], reward=True, verdict_evaluation='both',\n"
        "        reward_scheme=RewardScheme('shared', 'verdict-accuracy')) == a['outcome_feedback'])\n"
        "print(json.dumps(res))\n")
    assert out == [True] * 5
    assert seen == {"accept", "reject"}, "mock runs should exercise both replayed verdicts"


def test_prefix_episodes_unchanged(runs):
    for r in runs.values():
        pcr, pre = load(r["PC"]), load(r["prefix"])
        assert len(pcr["results"]) == 10
        assert pcr["results"][:5] == pre["results"][:5]
        assert all("controlled_bob" not in x for x in pcr["results"][:5])
        assert all("controlled_bob" in x for x in pcr["results"][5:])
        pc.check_same_prefix(r["B"], r["prefix"])


def test_cache_layout_and_payload(runs):
    r = runs[SEQS[0]]
    files = sorted(r["cache"].iterdir())
    assert [f.name[:5] for f in files] == ["0005-", "0006-", "0007-", "0008-", "0009-"]
    b = load(r["B"])
    for f in files:
        d = load(f)
        p = d["payload"]
        e = p["source"]["episode_index"]
        assert p["messages"] is None and p["raw_prefix_messages"] is None
        assert p[pc.PAYLOAD_FIELD] == pc.d22_messages(raw_of(b["results"][e]["agents"]["bob"]))
        assert all(x["actor"] == "bob" and x["phase"] == "task" for x in p["events"])
        assert {x["tool"] for x in p["events"]} <= {"save_final_answer", "get_log", "read_code", "read_source",
                                                     "write_test_file", "run_tests", "inspect_database",
                                                     "query_database", "resolve_records"}
        assert p["replayed_verdict"] == b["results"][e]["agents"]["bob"]["verdict"]
        assert p["slot"]["verdict_submission"] is None and p["slot"]["private_raw_log_retrieved"] is True
        assert d["identity"]["model"] == {"model": "gemini/gemini-3.1-flash-lite", "reasoning_effort": "high",
                                          "temperature": 1.0, "max_output_tokens": 64000}
        # trajectory: upstream controlled opening + B's task-phase slice, no communication turns
        traj = p["trajectory"]
        assert traj[0]["role"] == "system" and traj[1] == {"role": "_runner_active_episode_start"}
        assert traj[2] == {"role": "user", "content": b["results"][e]["agents"]["bob"]["own_task_prompt"]}
        assert traj[-1]["role"] == "tool" and traj[-1]["name"] == "get_log"
        assert all(m.get("name") != "send_message" for m in traj)


def test_cache_reused_and_changed_b_rejected(runs):
    r = runs[SEQS[0]]
    before = {f.name: (f.stat().st_mtime_ns, f.read_bytes()) for f in r["cache"].iterdir()}
    work = BASE / "cache_checks"
    work.mkdir(exist_ok=True)
    b_copy = work / "B_run.json"
    shutil.copyfile(r["B"], b_copy)
    out = run_py(
        "from src.hysteresis import partner_control as pc\n"
        "from pathlib import Path\n"
        "res = {}\n"
        f"paths = pc.ensure_cache(Path({str(r['B'])!r}), Path({str(r['cache'])!r}), Path({str(TREE)!r}))\n"
        "res['again'] = [p.name for p in paths]\n"
        f"cache2 = Path({str(work / 'cache2')!r}); b2 = Path({str(b_copy)!r})\n"
        "pc.ensure_cache(b2, cache2, Path(os.getcwd()))\n"
        "rec = json.loads(b2.read_text()); rb = rec['results'][6]['agents']['bob']; rb['reflection'] = 'changed'\n"
        "b2.write_text(json.dumps(rec, ensure_ascii=False, indent=2))\n"
        "try:\n    pc.ensure_cache(b2, cache2, Path(os.getcwd())); res['changed'] = 'no error'\n"
        "except ValueError as e:\n    res['changed'] = str(e)\n"
        f"cache3 = Path({str(work / 'cache3')!r}); shutil_src = Path({str(r['B'])!r})\n"
        "pc.ensure_cache(shutil_src, cache3, Path(os.getcwd()))\n"
        "f = sorted(cache3.iterdir())[2]; d = json.loads(f.read_text())\n"
        "d['payload']['replayed_verdict'] = 'reject' if d['payload']['replayed_verdict'] == 'accept' else 'accept'\n"
        "f.write_text(json.dumps(d, ensure_ascii=False, indent=2))\n"
        "try:\n    pc.ensure_cache(shutil_src, cache3, Path(os.getcwd())); res['tampered'] = 'no error'\n"
        "except ValueError as e:\n    res['tampered'] = str(e)\n"
        "(cache3 / 'extra.json').write_text('{}'); f.unlink()\n"
        "try:\n    pc.ensure_cache(shutil_src, cache3, Path(os.getcwd())); res['extra'] = 'no error'\n"
        "except ValueError as e:\n    res['extra'] = str(e)\n"
        "print(json.dumps(res))\n")
    after = {f.name: (f.stat().st_mtime_ns, f.read_bytes()) for f in r["cache"].iterdir()}
    assert after == before and sorted(out["again"]) == sorted(before)
    assert "was built from a B run.json with sha256" in out["changed"]
    assert "was modified after it was built" in out["tampered"]
    assert "holds" in out["extra"]


RESUME_SCRIPT = """
from pathlib import Path
from experiments import runner
from experiments.controlled import cached_model_settings
from experiments.prompts.system import initial_agent_messages
from experiments.protocol.rewards import reward_scheme_from_args
from src.hysteresis import run_arm, partner_control as pc
spec = json.loads(sys.argv[1]) if len(sys.argv) > 1 else SPEC
if spec['install']:
    pc.install(); pc.install()   # idempotent
out = []
for case in spec['cases']:
    argv = run_arm.upstream_argv('PC', spec['seq'], Path(spec['outdir']), resume_from=case['source'],
                                 pc_cache=spec['cache'])
    for old, new in case.get('replace', []):
        i = argv.index(old[0]); assert argv[i + 1] == old[1]; argv[i:i + 2] = new
    argv += case.get('add', [])
    args = runner.build_run_parser().parse_args(argv)
    runner.validate_run_args(args)
    args.controlled_bob_messages = pc.MESSAGE_POLICY
    rec = cached_model_settings(args.controlled_bob_cache)
    args.controlled_bob_task_model = rec['model']; args.bob_reasoning_effort = rec['reasoning_effort']
    args.bob_temperature = rec['temperature']; args.bob_max_output_tokens = rec['max_output_tokens']
    scheme = reward_scheme_from_args(args)
    base = {a: initial_agent_messages(agent_id=a, max_rounds=5 if a == 'bob' else args.max_rounds,
                                      reward_objective=args.reward and a != 'bob', reward_scheme=scheme)
            for a in ('alice', 'bob')}
    sel = runner._load_selected_tasks(args=args, repo_root=Path(os.getcwd()))
    try:
        results, msgs = runner._resume_state(args.resume_from, args=args, base_agent_messages=base,
                                             reward_scheme=scheme, manifest_path=sel.manifest_path,
                                             episode_count=len(sel.pairs))
        out.append(['ok', len(results)])
    except ValueError as e:
        out.append(['error', str(e)])
print(json.dumps(out))
"""


def _resume_cases(r, install, cases, outdir):
    spec = {"install": install, "seq": SEQS[0], "cache": str(r["cache"]), "outdir": str(outdir), "cases": cases}
    return run_py(f"SPEC = {json.dumps(spec)!r}\nSPEC = json.loads(SPEC)\n" + RESUME_SCRIPT)


def _truncated_pc(r, n, name):
    d = BASE / "resume_sources" / name
    d.mkdir(parents=True, exist_ok=True)
    rec = load(r["PC"])
    rec["results"] = rec["results"][:n]
    p = d / "run.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    return p


def test_resume_checks(runs):
    r = runs[SEQS[0]]
    outdir = BASE / "resume_checks"
    prefix = str(r["prefix"])
    part7 = str(_truncated_pc(r, 7, "part7"))
    part5 = str(_truncated_pc(r, 5, "part5"))
    cases = [
        {"source": prefix},                                                          # relaxed: ok
        {"source": prefix, "replace": [[["--char-limit", "200"], ["--char-limit", "300"]]]},
        {"source": prefix, "replace": [[["--reward-scope", "shared"], ["--reward-scope", "separate"]]]},
        {"source": prefix, "add": ["--no-verdict-review"]},
        {"source": prefix, "add": ["--controlled-bob-observed-verdict"]},
        {"source": prefix, "add": ["--no-reflection"]},
        {"source": part7},                                                           # own partial: ok
        {"source": part7, "replace": [[["--char-limit", "200"], ["--char-limit", "300"]]]},
        {"source": part7, "add": ["--controlled-bob-observed-verdict"]},
        {"source": part5},                                                           # no PC episode yet
    ]
    got = _resume_cases(r, True, cases, outdir)
    assert got[0] == ["ok", 5]
    assert got[1][0] == "error" and "char_limit" in got[1][1] and prefix in got[1][1]
    assert got[2][0] == "error" and "reward_scheme" in got[2][1] and "alice system prompt" in got[2][1]
    assert got[3][0] == "error" and "verdict_evaluation" in got[3][1]
    assert got[4][0] == "error" and "controlled_bob_observed_verdict" in got[4][1]
    assert got[5][0] == "error" and "reflection" in got[5][1]
    assert got[6] == ["ok", 7]
    assert got[7][0] == "error" and "char_limit" in got[7][1]
    assert got[8][0] == "error" and "controlled_bob_observed_verdict" in got[8][1]
    assert got[9][0] == "error" and "resume from the prefix" in got[9][1]
    assert not list(outdir.glob(".s2pc_resume_*")), "temporary resume copies must be removed"
    # without the patch, upstream refuses the live -> controlled resume (the reason for patch 4)
    plain = _resume_cases(r, False, [{"source": prefix}], outdir)
    assert plain[0][0] == "error"
    assert "controlled_bob_cache" in plain[0][1] and "bob system prompt differs" in plain[0][1]


def test_resume_crashed_pc_run(runs):
    r = runs[SEQS[0]]
    part7 = _truncated_pc(r, 7, "crash7")
    cache_before = {f.name: f.read_bytes() for f in r["cache"].iterdir()}
    out, p = run_arm("--arm", "PC", "--seq", str(SEQS[0]), "--resume-from", str(part7), "--b-run", str(r["B"]))
    resumed = load(out)
    full = load(r["PC"])
    assert {f.name: f.read_bytes() for f in r["cache"].iterdir()} == cache_before
    assert resumed["results"][:7] == load(part7)["results"]
    b = load(r["B"])
    for e in range(7, 10):
        ep = resumed["results"][e]
        assert ep["agents"]["bob"]["verdict"] == b["results"][e]["agents"]["bob"]["verdict"]
        assert [t["content"] for t in ep["channel_transcript"] if t["sender"] == "bob"] == \
            pc.d22_messages(raw_of(b["results"][e]["agents"]["bob"]))
        # deterministic mock: the resumed tail equals the uninterrupted run's tail
        assert ep["channel_transcript"] == full["results"][e]["channel_transcript"]
        assert ep["agents"]["alice"]["verdict"] == full["results"][e]["agents"]["alice"]["verdict"]
