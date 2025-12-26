#!/usr/bin/env python3
"""
CLI wrapper around civil_time.resolve_local_to_utc.

Examples:
  ./gimme_civil_time.py Europe/Rome 2025-01-15 12:00
  ./gimme_civil_time.py Europe/Rome 2025-10-26 02:30 --ambiguous earliest
  ./gimme_civil_time.py Europe/Rome 2025-03-30 02:30 --nonexistent shift_forward
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root (src/) is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import date, time

from civil_time.civil_time import (
    resolve_local_to_utc,
    AmbiguousLocalTime,
    NonExistentLocalTime,
)

def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date '{s}'. Use YYYY-MM-DD.") from e


def _parse_time(s: str) -> time:
    # Accept HH:MM or HH:MM:SS
    try:
        return time.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid time '{s}'. Use HH:MM or HH:MM:SS.") from e


def main() -> int:
    p = argparse.ArgumentParser(description="Resolve local civil time to a unique UTC instant.")
    p.add_argument("tzname", help="IANA timezone, e.g. Europe/Rome")
    p.add_argument("date", type=_parse_date, help="Local date (YYYY-MM-DD)")
    p.add_argument("time", type=_parse_time, help="Local time (HH:MM or HH:MM:SS)")

    p.add_argument(
        "--ambiguous",
        choices=["raise", "earliest", "latest"],
        default="raise",
        help="Policy for ambiguous (fall-back) local times.",
    )
    p.add_argument(
        "--nonexistent",
        choices=["raise", "shift_forward", "shift_backward"],
        default="raise",
        help="Policy for non-existent (spring-forward) local times.",
    )
    p.add_argument("--json", action="store_true", help="Print machine-friendly JSON.")
    args = p.parse_args()

    try:
        r = resolve_local_to_utc(
            args.date,
            args.time,
            args.tzname,
            ambiguous=args.ambiguous,
            nonexistent=args.nonexistent,
        )
    except AmbiguousLocalTime as e:
        print(f"[AMBIGUOUS] {e}", file=sys.stderr)
        return 3
    except NonExistentLocalTime as e:
        print(f"[NONEXISTENT] {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "tzname": r.tzname,
                    "local_date": args.date.isoformat(),
                    "local_time": args.time.isoformat(),
                    "utc": r.utc.isoformat(),
                    "offset_seconds": r.offset_seconds,
                    "is_dst": r.is_dst,
                    "fold": r.fold,
                },
                indent=2,
            )
        )
    else:
        print(f"tzname        : {r.tzname}")
        print(f"local         : {args.date.isoformat()} {args.time.isoformat()}")
        print(f"utc           : {r.utc.isoformat()}")
        print(f"offset_seconds: {r.offset_seconds:+d}")
        print(f"is_dst        : {r.is_dst}")
        print(f"fold          : {r.fold}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
