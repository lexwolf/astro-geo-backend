#!/usr/bin/env python3
"""
CLI helper to resolve a place name to its IANA timezone (via geocoding).

Examples:
  ./gimme_tzname.py "Parma, Italy"
  ./gimme_tzname.py "Parma, Ohio" --verbose
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root (src/) is on sys.path when executed as a file
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geo.geocode_city import (
    DEFAULT_CACHE,
    geocode,
    load_cache,
    save_cache,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Resolve a place name to an IANA timezone.")
    p.add_argument("query", help="Place query, e.g. 'Parma, Italy'")
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Cache file path.")
    p.add_argument("--min-delay", type=float, default=1.0, help="Min seconds between API calls.")
    p.add_argument("--verbose", action="store_true", help="Print full geocoding details.")
    p.add_argument("--json", action="store_true", help="Print machine-friendly JSON.")
    args = p.parse_args()

    user_agent = "astro-geo-backend/0.1 (Alessandro Veltri; contact: alessandro.veltri@gmail.com)"

    cache = load_cache(args.cache)
    last_t = None

    res, last_t, err = geocode(
        args.query,
        user_agent=user_agent,
        cache=cache,
        min_delay_s=args.min_delay,
        last_request_time=last_t,
        limit=1,
    )

    save_cache(args.cache, cache)

    if err:
        print(f"[ERR] {err}", file=sys.stderr)
        return 2

    assert res is not None

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "query": res.query,
                    "lat": res.lat,
                    "lon": res.lon,
                    "display_name": res.display_name,
                    "importance": res.importance,
                    "tzname": res.tzname,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(f"query        : {res.query}")
    print(f"display_name : {res.display_name}")
    print(f"lat, lon     : {res.lat:.6f}, {res.lon:.6f}")
    print(f"tzname       : {res.tzname}")

    if res.tzname is None:
        print(
            "\n[WARN] Timezone could not be resolved from coordinates.\n"
            "       Is 'timezonefinder' installed?",
            file=sys.stderr,
        )

    if args.verbose:
        print(f"importance   : {res.importance:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
