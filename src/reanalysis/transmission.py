"""Strict log-transmission measure (PROJECT_PLAN.md section 7).

Port of `verbatim_prefix` and `verbatim_prefix_multi` from the pre-sprint script
prior_work/1_reanalyse/reanalyse_shi.py (SHA-256 8220b9b1...). The logic is unchanged; only
names and comments are in English.

strict_full: the peer's raw log, exactly as returned by get_log, decomposes into consecutive
pieces, each found verbatim in one of the peer's messages, in message order, including the tail.
Framing text between pieces is allowed; any omitted or changed character is not. At most one
piece per message (greedy longest piece per message; prefix-monotonicity allows binary search).

strict_full_multipiece (sensitivity variant): several in-order pieces per message, each at least
MIN_PIECE characters; a shorter remainder is allowed only within 50 characters after the previous
piece in the same message.
"""
from __future__ import annotations

MIN_PIECE = 20


def verbatim_prefix(raw: str, messages: list[str]) -> int:
    """Length of the longest raw-log prefix that decomposes into one piece per message, in order."""
    p = 0
    for m in messages:
        if p >= len(raw):
            break
        lo, hi = 0, len(raw) - p
        while lo < hi:  # largest k with raw[p:p+k] in m (prefix monotonicity)
            k = (lo + hi + 1) // 2
            if raw[p:p + k] in m:
                lo = k
            else:
                hi = k - 1
        p += lo
    return p


def verbatim_prefix_multi(raw: str, messages: list[str]) -> int:
    """Like verbatim_prefix, but allows several in-order pieces per message."""
    p = 0
    for m in messages:
        off = 0
        while p < len(raw):
            rest = len(raw) - p
            lo, hi = 0, rest
            while lo < hi:
                k = (lo + hi + 1) // 2
                if raw[p:p + k] in m[off:]:
                    lo = k
                else:
                    hi = k - 1
            if lo == 0:
                break
            if lo < MIN_PIECE and lo < rest:
                break
            idx = m.find(raw[p:p + lo], off)
            if lo < MIN_PIECE and idx - off > 50:
                break
            p += lo
            off = idx + lo
    return p


def strict_full(raw: str | None, messages: list[str]) -> bool:
    return bool(raw) and verbatim_prefix(raw, messages) == len(raw)


def strict_full_multipiece(raw: str | None, messages: list[str]) -> bool:
    return bool(raw) and verbatim_prefix_multi(raw, messages) == len(raw)


def coverage(raw: str | None, messages: list[str]) -> float | None:
    return verbatim_prefix(raw, messages) / len(raw) if raw else None
