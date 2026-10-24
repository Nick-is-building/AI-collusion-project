"""Run one Study 2 arm for one task sequence through Shi et al.'s own runner (plan 9.1, 23.1).

    python -m src.hysteresis.run_arm --arm B --seq 1 --out-root results/study2/main \
        --resume-from <prefix run.json> --backend live --approved-stage study2 --group main

Arms (plan 9.1 table):
  prefix  episodes 1-5 constrained, fresh                     (spans throttled:*)
  Aprime  resume prefix, episodes 6-10 constrained              (throttled:*)
  B       resume prefix, episodes 6-10 open                     (throttled:5,no-throttle:*)
  Cprime  fresh, episodes 1-10 open                             (no-throttle:*)
  PC      resume prefix, episodes 6-10 open; Bob scripted from the finished B run of the same
          sequence (src/hysteresis/partner_control.py, D22)     (throttled:5,no-throttle:*)
A crashed run is continued with --resume-from its own last run.json (upstream resumes at episode
boundaries; a new run directory is always written, the source is never modified).

What this wrapper adds to upstream, and nothing else:
  - the working directory is the dedicated upstream copy (src/hysteresis/upstream_tree.py);
  - the prefix runs the first 5 pairs of the unchanged 10-pair manifest (upstream has no
    "stop after N episodes" option, and resume requires the same manifest path);
  - the status line from episode 6 (src/hysteresis/status_line.py);
  - the guarded completion (src/hysteresis/guard.py): caps, STOP file, response_model;
  - settings checks that upstream resume does not perform (models, effort, temperature, max
    tokens, litellm version), against Shi et al.'s settings;
  - a provenance sidecar `study2_meta.json` next to run.json.
Settings are Shi et al.'s (trace run_config): Gemini 3.1 Flash-Lite for both agents, temperature
1.0, max output 64,000, reasoning high, raw-only, char limit 200, 5 rounds, full history, shared
verdict-accuracy reward, reflection and verdict review on, --no-preflight (as upstream cli.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARMS = ("prefix", "Aprime", "B", "Cprime", "PC")
SPANS = {"prefix": "throttled:*", "Aprime": "throttled:*", "B": "throttled:5,no-throttle:*",
         "Cprime": "no-throttle:*", "PC": "throttled:5,no-throttle:*"}
BRANCHES = ("Aprime", "B", "PC")
PREFIX_EPISODES = 5
MODEL = "gemini/gemini-3.1-flash-lite"
LIVE_RESPONSE_MODEL = "gemini-3.1-flash-lite"   # observed in every A02-A04 live call
SETTINGS = {"temperature": 1.0, "max_output_tokens": 64000, "reasoning_effort": "high"}
LITELLM_VERSION = "1.94.1"
RESERVE_PER_CALL_USD = 0.06   # above the largest call in Shi's traces without cache (~140k in)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def upstream_argv(arm: str, seq: int, output_dir: Path, *, resume_from: str = "", pc_cache: str = "") -> list[str]:
    argv = ["--cross-episode-memory-scope", "full-history", "--verdict-policy", "raw-only",
            "--char-limit", "200", "--max-rounds", "5",
            "--manifest", f"task/task_sequences_50x10/rep{seq:03d}_sampled_manifest.json",
            "--run-label", f"s2_{arm}_rep{seq:03d}", "--output-dir", str(output_dir)]
    for agent in ("alice", "bob"):
        if agent == "bob" and arm == "PC":
            argv += ["--bob-model", "controlled"]
        else:
            argv += [f"--{agent}-model", MODEL, f"--{agent}-reasoning-effort", SETTINGS["reasoning_effort"],
                     f"--{agent}-temperature", str(SETTINGS["temperature"]),
                     f"--{agent}-max-output-tokens", str(SETTINGS["max_output_tokens"])]
        argv += [f"--{agent}-cross-episode-memory-length", "-1"]
    if arm == "PC":
        # The verdict flag only switches controlled mode on; partner_control replaces it per
        # episode with Bob's verdict from the B run. The message policy is set after parsing.
        argv += ["--controlled-bob-cache", pc_cache, "--controlled-bob-verdict", "accept",
                 "--controlled-bob-messages", "summary"]
    argv += ["--throttle-spans", SPANS[arm], "--reward-scope", "shared", "--reward-type", "verdict-accuracy",
             "--reflection", "--reward", "--verdict-review", "--no-preflight"]
    if resume_from:
        argv += ["--resume-from", resume_from]
    return argv


# Paths whose committed state a Study 2 run executes. Another session may edit unrelated tracked
# files in the same working tree (A06), so provenance is required for these paths only; the
# whole-tree dirty flag is still recorded in study2_meta.json.
PROVENANCE_PATHS = ("src/hysteresis", "scripts/study2", "src/runner", "src/upstream.py", "src/reanalysis",
                    "src/__init__.py", "configs", "third_party")


def study2_code_dirty() -> list[str]:
    import subprocess
    out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", *PROVENANCE_PATHS],
                         capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l.strip()]


def assert_study2_live_allowed(approved_stage):
    from src.runner.runner import LiveNotAuthorized
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise LiveNotAuthorized("live mode is disabled under pytest")
    if approved_stage != "study2":
        raise LiveNotAuthorized(f"live mode needs --approved-stage study2 (got {approved_stage!r})")
    dirty = study2_code_dirty()
    if dirty:
        raise LiveNotAuthorized(f"Study 2 code paths have uncommitted changes (provenance): {dirty[:5]}")


def check_record_settings(record: dict, arm: str):
    """Settings upstream's resume does not check (models, sampling, litellm), on a source run.json."""
    rc = record["run_config"]
    problems = []
    for agent in ("alice", "bob"):
        model = rc["models"][agent]
        if agent == "bob" and arm == "PC" and model == "controlled":
            model = rc.get("controlled_bob_task_model")   # PC's own partial run: Bob replays the cache
        if model != MODEL:
            problems.append(f"{agent} model {model!r}")
        for k, v in SETTINGS.items():
            if rc["llm_request_parameters"][agent].get(k) != v:
                problems.append(f"{agent} {k} {rc['llm_request_parameters'][agent].get(k)!r}")
    if rc.get("litellm_version") != LITELLM_VERSION:
        problems.append(f"litellm {rc.get('litellm_version')!r}")
    if problems:
        raise SystemExit(f"resume source settings differ from Shi et al.'s ({arm}): {problems}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arm", required=True, choices=ARMS)
    ap.add_argument("--seq", required=True, type=int)
    ap.add_argument("--out-root", required=True, help="Study 2 results root, e.g. results/study2")
    ap.add_argument("--group", required=True, help="sub-directory and cap group, e.g. p8 or main")
    ap.add_argument("--resume-from", default="", help="source run.json (prefix for branches, or own last run)")
    ap.add_argument("--b-run", default="", help="PC only: finished B run.json of the same sequence")
    ap.add_argument("--backend", required=True, choices=("mock", "live"))
    ap.add_argument("--approved-stage", default=None)
    ap.add_argument("--reserve-slots", type=int, default=1, help="workers that may have a call in flight")
    ap.add_argument("--caps-json", default="", help="mock only: caps for the guard test")
    ap.add_argument("--tree", default=str(ROOT / "work" / "study2" / "upstream"))
    a = ap.parse_args(argv)
    # Resolve every input path before the working directory changes to the upstream copy.
    a.resume_from = str(Path(a.resume_from).resolve()) if a.resume_from else ""
    a.b_run = str(Path(a.b_run).resolve()) if a.b_run else ""
    a.caps_json = str(Path(a.caps_json).resolve()) if a.caps_json else ""

    from src.hysteresis.upstream_tree import ensure_tree, verify_tree
    tree = ensure_tree(Path(a.tree))
    tree_meta = verify_tree(tree)
    out_root = Path(a.out_root).resolve()
    out_dir = out_root / a.group / f"rep{a.seq:03d}" / a.arm
    out_dir.mkdir(parents=True, exist_ok=True)
    stop_file = out_root / "STOP"

    if a.arm in BRANCHES and not a.resume_from:
        raise SystemExit(f"{a.arm} needs --resume-from (the prefix run.json, or its own last run)")
    if a.arm == "PC" and not a.b_run:
        raise SystemExit("PC needs --b-run (the finished B run.json of the same sequence)")

    if a.backend == "live":
        from src.runner.costs import load_yaml
        assert_study2_live_allowed(a.approved_stage)
        caps = load_yaml("caps.yaml")
        project_results = ROOT / "results" / "raw"
        import litellm
        backend, expected = litellm.completion, LIVE_RESPONSE_MODEL
    else:
        from src.hysteresis.mock_model import MOCK_RESPONSE_MODEL, mock_completion
        caps = (json.loads(Path(a.caps_json).read_text()) if a.caps_json else
                {"hard_cap_usd": 1e9, "stages": {"study2": 1e9}})
        project_results = None
        backend, expected = mock_completion, MOCK_RESPONSE_MODEL
    from src.runner.runner import git_state
    head, dirty = git_state()

    # Import upstream from the dedicated copy, with the copy as working directory.
    os.chdir(tree)
    sys.path.insert(0, str(tree))
    import experiments
    # src.runner imports upstream from the submodule before this point; both locations hold the
    # pinned commit (the copy is verified above, the submodule must be clean at that commit).
    from src.hysteresis.upstream_tree import check_import_location
    check_import_location(Path(experiments.__file__), tree)
    from experiments import agents as up_agents
    from experiments import runner as up_runner
    from experiments.llm import get_litellm_version

    if get_litellm_version() != LITELLM_VERSION:
        raise SystemExit(f"litellm {get_litellm_version()} != {LITELLM_VERSION}")

    from src.hysteresis import status_line
    from src.hysteresis.guard import Budget, guarded_completion
    status_line.install()
    budget = Budget(root=out_root, group=a.group, caps=caps, project_results=project_results)
    up_agents.completion = guarded_completion(backend, budget=budget,
                                              reserve_usd=RESERVE_PER_CALL_USD * max(a.reserve_slots, 1),
                                              expected_model=expected, stop_file=stop_file)

    pc_cache = ""
    if a.arm == "PC":
        from src.hysteresis import partner_control
        partner_control.install()
        pc_cache = str(out_dir / "bob_cache")
        partner_control.ensure_cache(Path(a.b_run), Path(pc_cache), tree)
        partner_control.check_same_prefix(Path(a.b_run), Path(a.resume_from))

    resume = a.resume_from
    source = None
    if resume:
        source = json.loads(Path(resume).read_text())
        check_record_settings(source, a.arm)

    args = up_runner.build_run_parser().parse_args(
        upstream_argv(a.arm, a.seq, out_dir, resume_from=resume, pc_cache=pc_cache))
    up_runner.validate_run_args(args)
    if a.arm == "PC":
        args.controlled_bob_messages = partner_control.MESSAGE_POLICY
    output_path = up_runner._create_output_path(args, tree)
    selected = up_runner._load_selected_tasks(args=args, repo_root=tree)
    verdict_by_ep, throttle_by_ep = up_runner._episode_policy_sequences(args, len(selected.pairs))
    if len(selected.pairs) != 10:
        raise SystemExit(f"manifest has {len(selected.pairs)} pairs, expected 10")
    if a.arm == "prefix":
        selected = up_runner.SelectedPairs(selected.pairs[:PREFIX_EPISODES], selected.manifest_path)
        verdict_by_ep, throttle_by_ep = verdict_by_ep[:PREFIX_EPISODES], throttle_by_ep[:PREFIX_EPISODES]

    meta_path = output_path.parent / "study2_meta.json"
    meta = {"arm": a.arm, "seq": a.seq, "group": a.group, "backend": a.backend,
            "run_dir": output_path.parent.name, "started_at": utc_now(), "git_head": head, "git_dirty": dirty,
            "study2_code_dirty": study2_code_dirty(),
            "upstream_copy": tree_meta, "argv": sys.argv, "upstream_argv": upstream_argv(
                a.arm, a.seq, out_dir, resume_from=resume, pc_cache=pc_cache),
            "resume_from": resume, "resume_from_sha256": sha256_file(resume) if resume else None,
            "resume_from_episodes": len(source["results"]) if source else 0,
            "b_run": a.b_run, "b_run_sha256": sha256_file(a.b_run) if a.b_run else None,
            "status_line": {"first_episode_index": status_line.FIRST_INDEX,
                            "limited": status_line.STATUS_LIMITED, "open": status_line.STATUS_OPEN},
            "throttle_by_episode": throttle_by_ep, "status": "running", "pid": os.getpid()}
    if a.arm == "PC":
        meta["pc_message_policy"] = partner_control.MESSAGE_POLICY
        meta["pc_note"] = ("run_config.controlled_bob_verdict is a placeholder; Bob's verdict per episode is "
                           "replayed from B (results[e].controlled_bob.verdict, agents.bob.verdict)")
    meta_path.write_text(json.dumps(meta, indent=1))

    def _terminate(signum, frame):   # SIGTERM -> normal exit, so the finally block records it
        raise SystemExit(f"terminated by signal {signum}")
    signal.signal(signal.SIGTERM, _terminate)
    status = "complete"
    try:
        up_runner._run_selected_episodes(args=args, repo_root=tree, output_path=output_path, selected=selected,
                                         verdict_policy_by_episode=verdict_by_ep,
                                         throttle_by_episode=throttle_by_ep)
    except BaseException as exc:
        status = f"failed: {type(exc).__name__}: {str(exc)[:500]}"
        raise
    finally:
        meta.update(status=status, finished_at=utc_now(),
                    episodes=len(json.loads(output_path.read_text())["results"]) if output_path.exists() else 0)
        meta_path.write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
