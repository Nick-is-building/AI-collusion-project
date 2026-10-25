"""A17 cell contexts: the D39/A16 cells (without its commission cell). Since A16's wrapper is committed (92d115a), the
contexts come from A16's builder (src.replay.a16.build_messages; A17: "reuse A16's model wrapper once it is
committed"). A first own version of the same table (same builders and arguments) gave byte-identical contexts on all
400 cells before the switch; tests/test_a17.py checks the contexts against the logged Flash-Lite hashes.

  cell (variant, version)   built as                                      Flash-Lite source of the same context
  R1      omission          variants.build(CUT, omission content)          a06:OMIT:<item>:R1:omission:<d>
  R4      omission          variants.build(R4, omission content)           a06:OMIT:<item>:R4:omission:<d>
  R2      omission/correct  variants.build(R2, omission content / None)    a13:LADDER:<item>:R2:<version>:<d>
  R1+CHK  omission/correct  a14.with_note_block(build(CUT, ...), "CHK")    a14:LOOK:<item>:CHK:<version>:<d>
  R0p     correct           variants.build(CUT, None)                      main:MAIN or a06:OMIT ...:R0p:correct:<d>
  R4      correct           variants.build(R4, None)                       main:MAIN or a06:OMIT ...:R4:correct:<d>
"""
from __future__ import annotations

from src.replay import a16

OM_VARIANTS = a16.OM_VARIANTS            # ("R1", "R4", "R2", "R1+CHK")
COR_VARIANTS = a16.COR_VARIANTS          # ("R0p", "R4", "R2", "R1+CHK")
BASE = a16.BASE
# Flash-Lite (stage, check, variant) that ran the same context, per (variant, version); R0p/R4 correct: main or a06
FLASH_LITE_SOURCE = {("R1", "omission"): [("a06", "OMIT", "R1")], ("R4", "omission"): [("a06", "OMIT", "R4")],
                     ("R2", "omission"): [("a13", "LADDER", "R2")], ("R2", "correct"): [("a13", "LADDER", "R2")],
                     ("R1+CHK", "omission"): [("a14", "LOOK", "CHK")], ("R1+CHK", "correct"): [("a14", "LOOK", "CHK")],
                     ("R0p", "correct"): [("main", "MAIN", "R0p"), ("a06", "OMIT", "R0p")],
                     ("R4", "correct"): [("main", "MAIN", "R4"), ("a06", "OMIT", "R4")]}


def build_messages(o: dict, variant: str, version: str) -> list:
    if (variant, version) == a16.COM_CELL:
        raise ValueError("A17 has no commission cell")
    return a16.build_messages(o, variant, version)
