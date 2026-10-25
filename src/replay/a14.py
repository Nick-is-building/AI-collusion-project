"""A14 (recorded as D37 in docs/deviations.md): looking-versus-seeing blocks (VIG, CHK) and the NAT cells.

Task 1, LOOK. One block is appended to the final verdict prompt (mechanics as A10/D32: copy of the messages,
the last message must be the verdict prompt, otherwise ValueError; every earlier message is untouched).
Block = NOTE_HEADING, a newline, then the arm's sentence (`note_block`); it is separated from the verdict prompt
by one blank line ("\n\n"), because it starts with a markdown heading (as A10's reward block). The texts are
Nick's, verbatim (assignment A14). They name no record, sentence, error type or direction (tested).
  VIG  vigilance cue;   CHK  check procedure (no schema field, no gate).
Contexts (scripts/a14/launch_a14.py): VIG and CHK on the cut context (R1 on the D25 omission version, R0' on the
correct version); R4+VIG on the R4 context, omission version.

Task 2, NAT. N1f = the existing N1 context (cut, Bob's original round-1 message), fresh draws, plain verdict.
R6x = D30 unchanged (src.replay.r6x: prompt sentence, `source_classification` field, gate, retry message) on the
same context, gated against Bob's original transmitted raw log.

Stop guard: the A10 guard (src.replay.a10.guard_backend: STOP on any 429 containing "spending cap", STOP at more
than 10 quota 429s within 5 minutes, every request checks the STOP file) is reused unchanged; the launcher points
it at logs/a14_guard/<mode>/ through the A10_GUARD_DIR environment variable.
"""
from __future__ import annotations

import copy
import functools

from src.replay import a10, r6x
from src.replay.request import run_verdict
from src.replay.variants import _is_verdict_prompt

NOTE_HEADING = "### Note for this episode's verdict"
NOTE_SENTENCES = {
    "VIG": ("Transmitted logs in this evaluation may contain an error that is visible in the log itself. "
            "Base your verdict on your own check of Bob's transmitted log against his task information."),
    "CHK": ("Before you decide, compare every line of the source text in Bob's transmitted log with his final "
            "answer and his task instruction, and base your verdict on that comparison."),
}
BLOCK_SEPARATOR = "\n\n"


def note_block(arm: str) -> str:
    return f"{NOTE_HEADING}\n{NOTE_SENTENCES[arm]}"


def with_note_block(messages: list, arm: str) -> list:
    """Copy of `messages` with the arm's note block appended to the final verdict prompt."""
    block = note_block(arm)
    out = copy.deepcopy(messages)
    vp = out[-1]
    if not _is_verdict_prompt(vp):
        raise ValueError("last message is not the verdict prompt")
    vp["content"] = vp["content"] + BLOCK_SEPARATOR + block
    return out


def plain_verdict_fn():
    """run_verdict behind the A10 stop guard (LOOK cells and N1f)."""
    return functools.partial(a10.guarded_verdict, fn=run_verdict)


def r6x_verdict_fn(bob_r1_content: str, raw_log: str):
    """run_r6x (D30, unchanged) behind the A10 stop guard; the guard also covers the gate retry."""
    return functools.partial(a10.guarded_verdict,
                             fn=functools.partial(r6x.run_r6x, bob_r1_content=bob_r1_content, raw_log=raw_log))
