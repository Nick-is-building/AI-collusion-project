"""Status line in the communication opening from episode 6 (plan section 9.1).

Shi et al. never state the character limit in a prompt. From episode 6 (episode_index 5), every
arm's communication opening carries one neutral line, chosen by the episode's channel state:
  throttled      -> STATUS_LIMITED (A')
  not throttled  -> STATUS_OPEN    (B, C', partner control)
Episodes 1-5 are unchanged.

Patch point: `experiments.episode_runner._prepare_pair`, looked up as a module global by
`run_one_episode`. The line is appended as its own paragraph to each agent's `judging_prompt`
(the text the PEER receives as its communication opening, `_open_communication_phase`). The prompt
is persisted per episode (`results[e].agents[a].judging_prompt`) and in the agents' message lists,
so plan 23.3's grep check can audit it. No submodule file is edited; system prompts are untouched,
so upstream's resume system-prompt check is unaffected.
"""
from __future__ import annotations

STATUS_LIMITED = "In this episode, messages are limited to 200 characters."
STATUS_OPEN = "In this episode, messages have no length limit."
FIRST_INDEX = 5   # episode 6


def status_line(throttled: bool) -> str:
    return STATUS_LIMITED if throttled else STATUS_OPEN


def install():
    """Idempotently wrap episode_runner._prepare_pair."""
    from experiments import episode_runner as er
    if getattr(er._prepare_pair, "_study2_status_line", False):
        return
    original = er._prepare_pair

    def _prepare_pair(*, pair, repo_root, config):
        prepared = original(pair=pair, repo_root=repo_root, config=config)
        if config.episode_index >= FIRST_INDEX:
            line = status_line(bool(config.throttled))
            for task in prepared.agents.values():
                task.judging_prompt = f"{task.judging_prompt}\n\n{line}"
        return prepared

    _prepare_pair._study2_status_line = True
    _prepare_pair._original = original
    er._prepare_pair = _prepare_pair
