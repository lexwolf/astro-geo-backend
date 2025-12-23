# civil_time.py
"""
Civil time -> UTC canonicalization using IANA tz rules (zoneinfo).

Goals:
- Convert (local date, local time, tzname) to a unique UTC datetime.
- Detect DST fall-back ambiguity (two valid instants) and handle it by policy.
- Detect DST spring-forward gaps (non-existent local times) and handle it by policy.
- Include metadata (offset, dst flag, fold) in the result.

Requires: Python 3.9+ (zoneinfo in stdlib)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


# -----------------------------
# Errors
# -----------------------------
class TimeResolutionError(ValueError):
    """Base class for civil time resolution failures."""


class AmbiguousLocalTime(TimeResolutionError):
    """Raised when a local time maps to two distinct instants and policy is 'raise'."""


class NonExistentLocalTime(TimeResolutionError):
    """Raised when a local time maps to no instant and policy is 'raise'."""


# -----------------------------
# Result
# -----------------------------
@dataclass(frozen=True)
class ResolutionResult:
    utc: datetime                 # timezone-aware UTC datetime
    tzname: str
    offset_seconds: int           # UTC offset at that instant (seconds)
    is_dst: bool | None           # best-effort; None if unknown
    fold: int                     # 0 or 1 (PEP 495), meaningful for ambiguous times


# -----------------------------
# Internals
# -----------------------------
def _roundtrip_matches(local_naive: datetime, aware_local: datetime) -> bool:
    """
    True if aware_local corresponds to the exact wall time local_naive in that zone.

    We roundtrip: local -> UTC -> local, and compare the wall-time.
    For non-existent local times, both folds fail this check.
    """
    back = aware_local.astimezone(timezone.utc).astimezone(aware_local.tzinfo)
    return back.replace(tzinfo=None) == local_naive


def _candidates_for(local_naive: datetime, tz: ZoneInfo) -> list[tuple[int, datetime]]:
    """
    Return list of (fold, aware_dt) candidates that roundtrip to local_naive.

    NOTE:
    For non-ambiguous local times, both fold=0 and fold=1 often roundtrip and
    represent the SAME instant. We collapse those to a single candidate.
    """
    out: list[tuple[int, datetime]] = []
    for fold in (0, 1):
        aware = local_naive.replace(tzinfo=tz, fold=fold)
        if _roundtrip_matches(local_naive, aware):
            out.append((fold, aware))

    if len(out) == 2:
        utc0 = out[0][1].astimezone(timezone.utc)
        utc1 = out[1][1].astimezone(timezone.utc)
        if utc0 == utc1:
            # Not truly ambiguous; fold has no effect here.
            return [out[0]]

    return out

def _best_effort_is_dst(local_aware: datetime) -> bool | None:
    """
    Best-effort DST flag using stdlib datetime.dst().
    Returns None if it cannot be evaluated.
    """
    try:
        dst = local_aware.dst()
        if dst is None:
            return None
        return dst.total_seconds() != 0
    except Exception:
        return None


# -----------------------------
# Public API
# -----------------------------
def resolve_local_to_utc(
    d: date,
    t: time,
    tzname: str,
    *,
    ambiguous: str = "raise",     # "raise" | "earliest" | "latest"
    nonexistent: str = "raise",   # "raise" | "shift_forward" | "shift_backward"
    shift_resolution: timedelta = timedelta(minutes=1),
    shift_search_limit: timedelta = timedelta(hours=24),
) -> ResolutionResult:
    """
    Convert local civil time (date, time, tzname) -> unique UTC datetime.

    Parameters
    ----------
    ambiguous:
        - "raise": raise AmbiguousLocalTime if two instants exist
        - "earliest": pick the earlier UTC instant
        - "latest": pick the later UTC instant

    nonexistent:
        - "raise": raise NonExistentLocalTime if no instant exists
        - "shift_forward": move forward until a valid local time exists
        - "shift_backward": move backward until a valid local time exists

    shift_resolution:
        Step used when shifting (default 1 minute). Keep it >= 1 minute unless
        you really need seconds.

    shift_search_limit:
        Maximum absolute search window during shifting (default 24 hours).

    Returns
    -------
    ResolutionResult
        Contains utc datetime and metadata (offset, is_dst, fold).
    """
    if ambiguous not in {"raise", "earliest", "latest"}:
        raise ValueError("ambiguous must be one of: 'raise', 'earliest', 'latest'")
    if nonexistent not in {"raise", "shift_forward", "shift_backward"}:
        raise ValueError("nonexistent must be one of: 'raise', 'shift_forward', 'shift_backward'")
    if shift_resolution <= timedelta(0):
        raise ValueError("shift_resolution must be positive")
    if shift_search_limit <= timedelta(0):
        raise ValueError("shift_search_limit must be positive")

    tz = ZoneInfo(tzname)
    local_naive = datetime.combine(d, t)

    candidates = _candidates_for(local_naive, tz)

    # -------------------------
    # Case 1: Ambiguous
    # -------------------------
    if len(candidates) == 2:
        if ambiguous == "raise":
            raise AmbiguousLocalTime(
                f"Ambiguous local time {local_naive} in {tzname}; "
                f"use ambiguous='earliest' or 'latest'."
            )
        # choose by earlier/later UTC
        if ambiguous == "earliest":
            chosen_fold, chosen = min(candidates, key=lambda x: x[1].astimezone(timezone.utc))
        else:
            chosen_fold, chosen = max(candidates, key=lambda x: x[1].astimezone(timezone.utc))

    # -------------------------
    # Case 2: Normal
    # -------------------------
    elif len(candidates) == 1:
        chosen_fold, chosen = candidates[0]

    # -------------------------
    # Case 3: Non-existent
    # -------------------------
    else:
        if nonexistent == "raise":
            raise NonExistentLocalTime(
                f"Non-existent local time {local_naive} in {tzname} (DST gap); "
                f"use nonexistent='shift_forward' or 'shift_backward'."
            )

        direction = +1 if nonexistent == "shift_forward" else -1
        probe = local_naive
        max_steps = int(shift_search_limit.total_seconds() // shift_resolution.total_seconds())

        for _ in range(max_steps):
            probe = probe + direction * shift_resolution
            cand = _candidates_for(probe, tz)
            if cand:
                # In a gap, the first valid time should typically be unique.
                chosen_fold, chosen = cand[0]
                break
        else:
            raise TimeResolutionError(
                f"Could not resolve non-existent time {local_naive} in {tzname} "
                f"within {shift_search_limit} using step {shift_resolution}."
            )

    utc_dt = chosen.astimezone(timezone.utc)
    offset = chosen.utcoffset()
    offset_seconds = int(offset.total_seconds()) if offset is not None else 0
    is_dst = _best_effort_is_dst(chosen)

    return ResolutionResult(
        utc=utc_dt,
        tzname=tzname,
        offset_seconds=offset_seconds,
        is_dst=is_dst,
        fold=chosen_fold,
    )


# -----------------------------
# Optional: tiny manual CLI smoke test
# -----------------------------
if __name__ == "__main__":
    # A few quick prints you can run with:
    #   python3 civil_time.py
    examples = [
        (date(2025, 1, 15), time(12, 0), "Europe/Rome", {}, "normal winter"),
        (date(2025, 7, 15), time(12, 0), "Europe/Rome", {}, "normal summer"),
        (date(2025, 10, 26), time(2, 30), "Europe/Rome", {"ambiguous": "earliest"}, "ambiguous earliest"),
        (date(2025, 10, 26), time(2, 30), "Europe/Rome", {"ambiguous": "latest"}, "ambiguous latest"),
        (date(2025, 3, 30), time(2, 30), "Europe/Rome", {"nonexistent": "shift_forward"}, "gap shift_forward"),
    ]

    for d, t, tzname, kw, label in examples:
        try:
            r = resolve_local_to_utc(d, t, tzname, **kw)
            print(f"{label:18}  local={d} {t} {tzname}  ->  utc={r.utc.isoformat()}  offset={r.offset_seconds} fold={r.fold} dst={r.is_dst}")
        except Exception as e:
            print(f"{label:18}  local={d} {t} {tzname}  ->  ERROR: {e}")
