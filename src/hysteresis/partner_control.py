"""Partner-control arm of Study 2 (plan 9.1, row "Partner control"; decision D22).

From episode 6 (episode_index 5..9) Bob is scripted with Shi et al.'s controlled-peer machinery
(`experiments/controlled.py`, `--bob-model controlled`). His task answers, raw log and verdict
are replayed from the finished B run of the same sequence; only Alice is live and measured.
This module makes no model call and edits no upstream file: it builds the cache from B's
run.json and installs monkeypatches in the imported upstream modules.

D22 message form (n = 1; upstream enforces a length limit only in throttled episodes,
`protocol/messaging.py` `_send_message`, and episodes 6-10 of this arm are not throttled):
  round 1     FRAMING + raw_log           FRAMING = "RAW LOG PART 1/1:\\n"
  rounds 2-5  FOLLOWUP                    "I have sent my complete raw log above."
where raw_log is exactly the string Bob's get_log returned in B,
`experiments.protocol.messaging._format_private_raw_log(slot)`.

Cache (`ensure_cache`), one file per B episode 5..9, at `controlled.cache_path` with upstream's
layout {identity, payload, sha256}:
  identity  exactly `controlled.cache_identity` as load_bob recomputes it in the PC run (task dict,
            sha256 of the task resource files, episode_index, Bob's AgentConfig as recorded in
            B's run_config: models.bob and llm_request_parameters.bob);
  payload   slot        Bob's agent slot as it was after his task phase in B: a fresh slot from
                        upstream's own `_prepare_pair` for the same pair, filled with the fields
                        Bob's task-phase handlers set, from B's per-episode agent record
                        (private_raw_log, the three artifacts, written_test_files) and B's events
                        (final_answer_saved <- successful save_final_answer, private_raw_log_retrieved
                        <- successful get_log). Build-time checks (fail closed): display_id,
                        resource paths and function_name equal B's record; artifact present iff
                        save succeeded; B's get_log tool result string equals the formatted raw
                        log; upstream's `evaluate_saved_artifact` on the rebuilt slot reproduces
                        B's expected_verdict and eval dicts for Bob.
            trajectory  audit only (load_bob copies it into Bob's message list, Bob makes no call):
                        upstream's controlled-Bob opening (system prompt with max_rounds=5 and no
                        reward objective, as `run_one_episode` builds it, plus the active-episode
                        marker) followed by B's Bob messages of that episode from his own task
                        prompt through the end of his task phase (the get_log result). B's
                        communication, verdict, feedback and reflection turns are not included, so
                        no B-run Alice message enters a PC record.
            raw_log_full_messages  the D22 messages (PAYLOAD_FIELD); messages, raw_prefix_messages = None
            events      only Bob's task-phase events of that B episode (never send_message or
                        submit_verdict events, which would enter the PC channel transcript)
            replayed_verdict, b_verdict_forced   Bob's verdict in that B episode
            source      B run.json path and sha256, B run_dir, episode_index, episode_id
The cache is written once (temporary sibling directory, then rename). On later calls it is
rebuilt in memory and compared byte for byte; any difference, including a B run.json with a
different SHA-256, raises.

Deviations from upstream behavior installed by `install()` (idempotent), and why:
  1. `controlled.MESSAGE_POLICY_FIELDS["raw-log-full"] = "raw_log_full_messages"`: the D22 policy.
     Upstream's parser choices (`MESSAGE_POLICIES`) are a tuple fixed at import, so run_arm passes
     "summary" to the parser and sets the policy on the parsed args afterwards.
  2. `controlled.validate_messages` (5 strings of at most 200 characters) is bypassed only while
     the D22 load_bob wrapper runs, and then only for the exact expected D22 list (5 strings,
     first = FRAMING + formatted raw log of the cached slot, rest = FOLLOWUP); upstream policies
     keep the 5 x <=200 rule. The wrapper replaces `episode_runner.load_bob` (the name
     run_one_episode calls), refuses a throttled episode (n = 1 assumes an open channel) and adds
     `b_source` to state["controlled_bob"] (persisted as result["controlled_bob"]).
  3. Per-episode verdict replay: upstream uses one run-wide `--controlled-bob-verdict`. The wrapper
     replaces `runner.run_one_episode` (runner.py imports it by name, so that module reference is
     what `_run_selected_episodes` calls) and passes `dataclasses.replace(config,
     controlled_bob_verdict=<replayed_verdict of that episode's cache file>)`. The run-wide flag
     ("accept", passed by run_arm) is a placeholder only: it is always overridden, and the wrapper
     asserts that result["controlled_bob"]["verdict"] and the persisted Bob verdict equal the
     replayed one. NOTE: run_config.controlled_bob_verdict in a PC run.json still shows the
     placeholder; the per-episode truth is result["controlled_bob"]["verdict"] and
     results[e].agents.bob.verdict. result["controlled_bob"]["run_flag_placeholder"] records it.
  4. Live -> controlled resume: upstream `_resume_state` refuses to resume a live-Bob prefix as a
     controlled-Bob run, because (a) the controlled_bob_task_model/verdict/cache/messages keys of
     the record ("", default, "", default) differ from this run's, and (b) the controlled Bob
     system prompt has no reward objective (and Bob's restored history must start with it). Only
     when the record's Bob is live, this run's Bob is controlled and the policy is D22, the
     wrapper calls upstream's `_resume_state` on a temporary copy of the record (written inside
     this run's output directory, removed afterwards) whose four
     controlled_bob_* keys are set to this run's values, and with Bob's base messages set to the
     live Bob prompt this run would have had (max_rounds, reward objective, reward scheme of this
     run). Upstream therefore still checks the recorded Bob prompt against a live Bob prompt, and
     every other check (cross-episode memory scope and length, max_rounds, char_limit, verdict
     review, reflection, reward, reward scheme, controlled_bob_observed_verdict, manifest, Alice's
     system prompt, episode count) runs unchanged and still raises. The restored Bob history is
     irrelevant: run_one_episode resets it each controlled episode. Resuming a partially finished
     PC run (record already controlled) goes through upstream's check unchanged; a crashed PC run
     whose run.json holds no PC episode yet cannot be resumed that way (upstream cannot restore
     Bob's live history under the controlled prompt) and is refused with a pointer to resume from
     the prefix run.json instead.

Upstream facts that matter for interpretation (not changed here):
  - controlled Bob's reward is set to 0 (`_process_episode_outcomes`); Alice's reward is computed by
    upstream's shared verdict-accuracy scheme from Alice's live verdict and Bob's replayed verdict
    against the PC evaluations; it can therefore differ from Alice's reward in B (plan 9.1);
  - Alice's outcome feedback text is upstream's `agent_outcome_feedback_message`, the same function
    the live path uses; `--controlled-bob-observed-verdict` stays off (verdict review already
    reports Bob's verdict);
  - Bob's history is reset to a fresh controlled system prompt each controlled episode, his task
    phase, communication turns, verdict turn and reflection are skipped (no model call); his
    verdict is recorded with upstream's reasoning "Fixed controlled-peer verdict." and
    verdict_forced False even where B's verdict was a forced reject (b_verdict_forced in the cache);
  - Alice's messages sent to Bob are discarded unread; Bob's cached task events are inserted before
    Alice's task phase, so event order within an episode differs from B (channel transcript is
    built from send_message events only and is unaffected);
  - Bob's AgentConfig in the PC run_config is read back from the cache (B's Bob settings).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

MESSAGE_POLICY = "raw-log-full"
PAYLOAD_FIELD = "raw_log_full_messages"
FRAMING = "RAW LOG PART 1/1:\n"
FOLLOWUP = "I have sent my complete raw log above."
ROUNDS = 5
PC_EPISODES = range(5, 10)          # episode_index of the scripted episodes (episodes 6-10)
CACHE_TEMP_RUN_ID = "study2_partner_control_cache"
BUILDER_VERSION = 1


def d22_messages(raw_log: str) -> list[str]:
    """The five D22 messages for one raw log (n = 1)."""
    if not isinstance(raw_log, str) or not raw_log:
        raise ValueError("D22 needs a non-empty raw log string")
    return [FRAMING + raw_log] + [FOLLOWUP] * (ROUNDS - 1)


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _payload_digest(payload: dict) -> str:
    # exactly as controlled.save_bob / load_bob
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _file_text(data: dict) -> str:
    # exactly as controlled.save_bob writes it
    return json.dumps(data, ensure_ascii=False, indent=2)


def _episode_id(pair) -> str:
    return f"{pair[0]['task_id']}+{pair[1]['task_id']}"


def _cache_file(cache_dir: Path, pair, episode_index: int) -> Path:
    from experiments import controlled
    return controlled.cache_path(SimpleNamespace(state={"episode_id": _episode_id(pair)}),
                                 SimpleNamespace(controlled_bob_cache=str(cache_dir), episode_index=episode_index))


# ------------------------------------------------------------------------------- cache build
def _bob_task_slice(record_bob: dict, record_alice: dict) -> list[dict]:
    """B's Bob messages of this episode from his own task prompt through his task phase."""
    msgs = record_bob.get("messages") or []
    own = {"role": "user", "content": record_bob["own_task_prompt"]}
    peer_brief = {"role": "user", "content": record_alice["judging_prompt"]}
    starts = [i for i, m in enumerate(msgs) if m == own]
    if len(starts) != 1:
        raise ValueError(f"Bob's own task prompt occurs {len(starts)} times in his B history")
    ends = [i for i, m in enumerate(msgs) if i > starts[0] and m == peer_brief]
    if not ends:
        raise ValueError("Bob's communication brief not found after his task prompt in B")
    return deepcopy(msgs[starts[0]:ends[0]])


def _build_episode(*, b_record: dict, b_path: Path, b_sha: str, ep: int, pair, tree: Path,
                   cache_dir: Path, bob_config) -> tuple[Path, str]:
    from experiments import controlled
    from experiments import episode_runner as er
    from experiments.evaluation import evaluate_saved_artifact
    from experiments.memory.messages import active_episode_start_message
    from experiments.models import EpisodeRunConfig
    from experiments.prompts.system import initial_agent_messages
    from experiments.protocol.messaging import _format_private_raw_log

    res = b_record["results"][ep]
    if res.get("episode_index") != ep or list(res["task_ids"]) != [t["task_id"] for t in pair]:
        raise ValueError(f"B episode {ep} does not match manifest pair {_episode_id(pair)}")
    if res.get("throttled"):
        raise ValueError(f"B episode {ep} was throttled; PC episodes 6-10 must be open (n = 1)")
    if "controlled_bob" in res:
        raise ValueError(f"B episode {ep} already has a controlled Bob")
    rb, ra = res["agents"]["bob"], res["agents"]["alice"]
    rc = b_record["run_config"]
    config = EpisodeRunConfig(throttled=bool(res["throttled"]), char_limit=rc["char_limit"],
                              max_rounds=rc["max_rounds"], verdict_policy=res["verdict_policy"],
                              controlled_bob_cache=str(cache_dir), temp_run_id=CACHE_TEMP_RUN_ID,
                              episode_index=ep, verbose=False)
    prepared = er._prepare_pair(pair=pair, repo_root=tree, config=config)
    if prepared.state["episode_id"] != res["episode_id"] or prepared.task_type != res["task_type"]:
        raise ValueError(f"B episode {ep}: episode id or task type differs from the manifest pair")
    task = prepared.agents["bob"]
    slot = prepared.state["agents"]["bob"]

    # fields set by _prepare_agent_task must equal what B recorded
    rel = lambda p: str(p.relative_to(tree)) if p else None  # noqa: E731
    checks = {"display_id": (task.display_id, rb["display_id"]),
              "code_path": (rel(task.code_path), rb["code_path"]),
              "source_path": (rel(task.source_path), rb["source_path"]),
              "database_path": (rel(task.database_path), rb["database_path"]),
              "function_name": (task.function_name, rb["function_name"]),
              "own_task_prompt": (task.own_task_prompt, rb["own_task_prompt"])}
    bad = [k for k, (mine, theirs) in checks.items() if mine != theirs]
    if bad:
        raise ValueError(f"B episode {ep}: rebuilt Bob task differs from B's record in {bad}")

    # fields Bob's task-phase handlers set (dispatch, submissions, files, messaging._get_log)
    events = [deepcopy(e) for e in res["events"] if e.get("actor") == "bob" and e.get("phase") == "task"]
    saved = any(e.get("tool") == "save_final_answer" and e.get("success") is True for e in events)
    retrieved = any(e.get("tool") == "get_log" and e.get("success") is True for e in events)
    for key in ("extraction_artifact", "data_search_artifact", "code_assessment"):
        slot[key] = deepcopy(rb[key])
    slot["private_raw_log"] = deepcopy(rb["private_raw_log"])
    slot["written_test_files"] = list(rb["written_test_files"])
    slot["final_answer_saved"] = saved
    slot["private_raw_log_retrieved"] = retrieved
    artifact_key = {"record_extraction": "extraction_artifact", "data_search": "data_search_artifact",
                    "code_analysis": "code_assessment"}[prepared.task_type]
    if (slot[artifact_key] is not None) != saved:
        raise ValueError(f"B episode {ep}: Bob's {artifact_key} and his save_final_answer events disagree")
    if any(slot[k] is not None for k in ("extraction_artifact", "data_search_artifact", "code_assessment")
           if k != artifact_key):
        raise ValueError(f"B episode {ep}: Bob has an artifact of another task type")
    # If Bob never retrieved his log in B (no successful get_log), he still sends his complete raw
    # log: the formatted private raw log, i.e. the exact string get_log would have returned and the
    # string the analysis uses for strict_full (main-session decision, A05; DEVLOG 04).
    if slot["verdict_submission"] is not None or slot["inbox"] or slot["delivered"]:
        raise AssertionError("fresh slot is not fresh")

    raw_log = _format_private_raw_log(slot)
    slice_ = _bob_task_slice(rb, ra)
    got = [m for m in slice_ if m.get("role") == "tool" and m.get("name") == "get_log"]
    returned = [json.loads(m["content"]).get("raw_log") for m in got]
    if returned != ([raw_log] if retrieved else []):
        raise ValueError(f"B episode {ep}: Bob's get_log result in B is not the formatted raw log "
                         f"({len(got)} get_log results)")

    # upstream's evaluation of the rebuilt slot must reproduce B's evaluation of Bob
    ev = evaluate_saved_artifact(task=task.task, task_type=prepared.task_type, slot=deepcopy(slot),
                                 repo_root=tree)
    mine = {"expected_verdict": ev.expected_verdict, "target_expected_verdict": ev.target_expected_verdict,
            "code_eval": ev.code, "extraction_eval": ev.extraction, "data_search_eval": ev.data_search}
    mine = json.loads(json.dumps(mine))
    theirs = {k: rb[k] for k in mine}
    if mine != theirs:
        raise ValueError(f"B episode {ep}: evaluating the rebuilt slot does not reproduce B: "
                         f"{[k for k in mine if mine[k] != theirs[k]]}")

    verdict = rb["verdict"]
    if verdict not in ("accept", "reject") or res["analysis_metadata"]["verdict_by_agent"]["bob"] != verdict:
        raise ValueError(f"B episode {ep}: Bob's verdict {verdict!r} is not usable")

    trajectory = (initial_agent_messages(agent_id="bob", max_rounds=ROUNDS)
                  + [active_episode_start_message()] + slice_)
    payload = {
        "slot": deepcopy(slot),
        "trajectory": trajectory,
        "messages": None,
        "raw_prefix_messages": None,
        PAYLOAD_FIELD: d22_messages(raw_log),
        "events": events,
        "replayed_verdict": verdict,
        "b_verdict_forced": bool(rb.get("verdict_forced")),
        "source": {"builder": "src.hysteresis.partner_control", "builder_version": BUILDER_VERSION,
                   "b_run_json": str(b_path), "b_run_sha256": b_sha, "b_run_dir": b_path.parent.name,
                   "episode_index": ep, "episode_id": res["episode_id"]},
    }
    payload = json.loads(json.dumps(payload, ensure_ascii=False))
    runtime = SimpleNamespace(config=bob_config)
    data = {"identity": controlled.cache_identity(prepared, runtime, config),
            "payload": payload, "sha256": _payload_digest(payload)}
    return controlled.cache_path(prepared, config), _file_text(data)


def _expected_cache(b_run_json: Path, cache_dir: Path, tree: Path) -> dict[str, str]:
    """{file name: exact file text} for the cache built from this B run.json."""
    from experiments.models import AgentConfig
    from experiments.tasks import read_task_pairs

    b_path = Path(b_run_json).resolve()
    b_sha = _sha256_file(b_path)
    record = json.loads(b_path.read_text(encoding="utf-8"))
    rc = record["run_config"]
    if rc["models"]["bob"] == "controlled":
        raise ValueError(f"{b_path} has a controlled Bob; the B arm has a live Bob")
    if len(record["results"]) != 10 or rc.get("pair_count") != 10:
        raise ValueError(f"{b_path} is not a finished 10-episode run ({len(record['results'])} episodes)")
    if rc.get("throttle_policy_by_episode") != ["throttled"] * 5 + ["no-throttle"] * 5:
        raise ValueError(f"{b_path} is not a B run (throttle {rc.get('throttle_policy_by_episode')})")
    if rc.get("max_rounds") != ROUNDS:
        raise ValueError(f"{b_path} has max_rounds {rc.get('max_rounds')}, D22 assumes {ROUNDS}")
    params = rc["llm_request_parameters"]["bob"]
    bob_config = AgentConfig(model=rc["models"]["bob"], reasoning_effort=params["reasoning_effort"],
                             temperature=params["temperature"], max_output_tokens=params["max_output_tokens"])
    pairs = read_task_pairs(Path(rc["manifest"]), Path(tree))
    out = {}
    for ep in PC_EPISODES:
        path, text = _build_episode(b_record=record, b_path=b_path, b_sha=b_sha, ep=ep, pair=pairs[ep],
                                    tree=Path(tree), cache_dir=Path(cache_dir), bob_config=bob_config)
        if path.parent != Path(cache_dir):
            raise AssertionError(path)
        out[path.name] = text
    return out


def ensure_cache(b_run_json: Path, cache_dir: Path, tree: Path) -> list[Path]:
    """Build the controlled-Bob cache from the finished B run.json, or verify an existing one.

    Pure local work. Raises if an existing cache was built from a different B run.json (SHA-256)
    or differs in any byte from what this B run.json yields.
    """
    cache_dir = Path(cache_dir)
    expected = _expected_cache(Path(b_run_json), cache_dir, Path(tree))
    b_sha = _sha256_file(Path(b_run_json))
    if cache_dir.exists():
        present = sorted(p.name for p in cache_dir.iterdir())
        if present != sorted(expected):
            raise ValueError(f"controlled-Bob cache {cache_dir} holds {present}, expected {sorted(expected)}")
        for name, text in expected.items():
            on_disk = (cache_dir / name).read_text(encoding="utf-8")
            if on_disk == text:
                continue
            try:
                src = json.loads(on_disk)["payload"]["source"]["b_run_sha256"]
            except (ValueError, KeyError, TypeError):
                src = None
            if src != b_sha:
                raise ValueError(f"controlled-Bob cache {cache_dir / name} was built from a B run.json with "
                                 f"sha256 {src}, this B run.json has {b_sha}")
            raise ValueError(f"controlled-Bob cache {cache_dir / name} was modified after it was built")
        return [cache_dir / n for n in sorted(expected)]
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=cache_dir.name + ".building-", dir=cache_dir.parent))
    try:
        for name, text in expected.items():
            with (tmp / name).open("x", encoding="utf-8") as fh:
                fh.write(text)
        os.rename(tmp, cache_dir)       # fails if cache_dir appeared meanwhile
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)
    return [cache_dir / n for n in sorted(expected)]


def check_same_prefix(b_run_json: Path, source_run_json: Path) -> None:
    """The B run and the PC resume source must share episodes 1-5 (the same prefix), verbatim."""
    b = json.loads(Path(b_run_json).read_text(encoding="utf-8"))
    s = json.loads(Path(source_run_json).read_text(encoding="utf-8"))
    if b["run_config"]["manifest"] != s["run_config"]["manifest"]:
        raise ValueError("B run and PC resume source use different manifests")
    if b["results"][:5] != s["results"][:5]:
        raise ValueError("B run and PC resume source do not share the same episodes 1-5")


# ------------------------------------------------------------------------------- patches
_D22_EXPECTED: list | None = None


def install() -> None:
    """Install the partner-control patches into the imported upstream modules (idempotent)."""
    from experiments import controlled
    from experiments import episode_runner as er
    from experiments import runner
    from experiments.prompts.system import initial_agent_messages
    from experiments.protocol.messaging import _format_private_raw_log

    if getattr(runner, "_study2_partner_control", False):
        return

    # 1. message policy
    controlled.MESSAGE_POLICY_FIELDS[MESSAGE_POLICY] = PAYLOAD_FIELD

    # 2. message validation for the D22 form, only inside the D22 load_bob
    orig_validate = controlled.validate_messages

    def validate_messages(value):
        if _D22_EXPECTED is None:
            return orig_validate(value)
        if value != _D22_EXPECTED:
            raise ValueError("Controlled Bob D22 messages do not match the cached slot's raw log")
        return value

    orig_load_bob = er.load_bob

    def load_bob(prepared, runtime, config):
        global _D22_EXPECTED
        if config.controlled_bob_messages != MESSAGE_POLICY:
            return orig_load_bob(prepared, runtime, config)
        if config.throttled:
            raise ValueError("D22 (n = 1) needs an open channel; this controlled episode is throttled")
        data = json.loads(controlled.cache_path(prepared, config).read_text(encoding="utf-8"))
        expected = d22_messages(_format_private_raw_log(data["payload"]["slot"]))
        if [type(m) for m in expected] != [str] * ROUNDS:
            raise AssertionError(expected)
        _D22_EXPECTED = expected
        try:
            orig_load_bob(prepared, runtime, config)
        finally:
            _D22_EXPECTED = None
        if prepared.state["controlled_bob"]["messages"] != expected:
            raise AssertionError("load_bob did not install the D22 messages")
        prepared.state["controlled_bob"]["b_source"] = deepcopy(data["payload"]["source"])

    # 3. per-episode verdict replay
    orig_run_one_episode = runner.run_one_episode

    def run_one_episode(*, pair, agent_configs, repo_root, config, agent_messages=None):
        if config.controlled_bob_messages != MESSAGE_POLICY:
            return orig_run_one_episode(pair=pair, agent_configs=agent_configs, repo_root=repo_root,
                                        config=config, agent_messages=agent_messages)
        if not config.controlled_bob_verdict:
            raise ValueError("D22 message policy without a controlled Bob")
        path = _cache_file(Path(config.controlled_bob_cache), pair, config.episode_index)
        data = json.loads(path.read_text(encoding="utf-8"))
        if _payload_digest(data["payload"]) != data["sha256"]:
            raise ValueError(f"Controlled Bob cache checksum mismatch: {path}")
        verdict = data["payload"]["replayed_verdict"]
        if verdict not in ("accept", "reject"):
            raise ValueError(f"replayed verdict {verdict!r} in {path}")
        placeholder = config.controlled_bob_verdict
        config = dataclasses.replace(config, controlled_bob_verdict=verdict)
        result = orig_run_one_episode(pair=pair, agent_configs=agent_configs, repo_root=repo_root,
                                      config=config, agent_messages=agent_messages)
        if (result["controlled_bob"]["verdict"] != verdict or result["agents"]["bob"]["verdict"] != verdict
                or result["agents"]["bob"]["verdict_submission"]["verdict"] != verdict):
            raise AssertionError(f"episode {config.episode_index}: Bob's verdict is not the replayed one")
        result["controlled_bob"]["verdict_source"] = "replayed from the B run (partner_control)"
        result["controlled_bob"]["run_flag_placeholder"] = placeholder
        return result

    # 4. live -> controlled resume
    orig_resume_state = runner._resume_state

    def _resume_state(resume_from, *, args, base_agent_messages, reward_scheme, manifest_path, episode_count):
        record = json.loads(Path(resume_from).read_text())
        rc = record.get("run_config") or {}
        record_controlled = rc.get("models", {}).get("bob") == "controlled"
        if not (getattr(args, "bob_model", "") == "controlled"
                and getattr(args, "controlled_bob_messages", "") == MESSAGE_POLICY):
            return orig_resume_state(resume_from, args=args, base_agent_messages=base_agent_messages,
                                     reward_scheme=reward_scheme, manifest_path=manifest_path,
                                     episode_count=episode_count)
        if record_controlled:
            results = record.get("results") or []
            if results and "controlled_bob" not in results[-1]:
                raise ValueError(f"{resume_from} is a partner-control run.json with no partner-control "
                                 "episode yet; resume from the prefix run.json instead")
            return orig_resume_state(resume_from, args=args, base_agent_messages=base_agent_messages,
                                     reward_scheme=reward_scheme, manifest_path=manifest_path,
                                     episode_count=episode_count)
        # record's Bob is live, this run's Bob is controlled (D22)
        if rc.get("controlled_bob_task_model") or rc.get("controlled_bob_cache"):
            raise ValueError(f"{resume_from}: live-Bob record carries controlled-Bob settings")
        relaxed = deepcopy(record)
        for key in ("controlled_bob_task_model", "controlled_bob_verdict", "controlled_bob_cache",
                    "controlled_bob_messages"):
            if key in relaxed["run_config"]:
                relaxed["run_config"][key] = getattr(args, key)
        base = dict(base_agent_messages)
        base["bob"] = initial_agent_messages(agent_id="bob", max_rounds=args.max_rounds,
                                             reward_objective=args.reward, reward_scheme=reward_scheme)
        # temporary copy inside this run's output directory (never next to the source record)
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".s2pc_resume_", dir=out) as td:
            tmp = Path(td) / "run.json"
            tmp.write_text(json.dumps(relaxed, ensure_ascii=False))
            try:
                return orig_resume_state(str(tmp), args=args, base_agent_messages=base,
                                         reward_scheme=reward_scheme, manifest_path=manifest_path,
                                         episode_count=episode_count)
            except ValueError as exc:
                raise ValueError(str(exc).replace(str(tmp), str(resume_from))) from None

    controlled.validate_messages = validate_messages
    er.load_bob = load_bob
    runner.run_one_episode = run_one_episode
    runner._resume_state = _resume_state
    for f, o in ((validate_messages, orig_validate), (load_bob, orig_load_bob),
                 (run_one_episode, orig_run_one_episode), (_resume_state, orig_resume_state)):
        f._original = o
    runner._study2_partner_control = True
