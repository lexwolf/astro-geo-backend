#!/usr/bin/env python3
"""
CLI wrapper around geo.geocode_city.geocode()

Examples:
  ./gimme_geocode_city.py "Cosenza, Italy"
  ./gimme_geocode_city.py "Quito, Ecuador" --json
  ./gimme_geocode_city.py --file cities.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root (src/) is on sys.path when executed as a file
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geo.geocode_city import DEFAULT_CACHE, geocode, load_cache, save_cache  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Geocode city/place names to coordinates.")
    p.add_argument("query", nargs="?", help="Place query, e.g. 'Cosenza, Italy'")
    p.add_argument("--file", type=Path, help="Read one query per line from a file.")
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Cache file path.")
    p.add_argument("--min-delay", type=float, default=1.0, help="Min seconds between API calls.")
    p.add_argument("--json", action="store_true", help="Print JSON output.")
    p.add_argument("--verbose", action="store_true", help="Print display_name and importance.")
    args = p.parse_args()

    user_agent = "astro-geo-backend/0.1 (Alessandro Veltri; contact: alessandro.veltri@gmail.com)"

    cache = load_cache(args.cache)
    last_t = None

    if args.file:
        try:
            queries = [line.strip() for line in args.file.read_text(encoding="utf-8").splitlines()]
            queries = [q for q in queries if q and not q.startswith("#")]
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 2
    elif args.query:
        queries = [args.query]
    else:
        print("Provide a query string or --file.", file=sys.stderr)
        return 2

    results_out = []
    exit_code = 0

    for q in queries:
        res, last_t, err = geocode(
            q,
            user_agent=user_agent,
            cache=cache,
            min_delay_s=args.min_delay,
            last_request_time=last_t,
            limit=1,
        )
        if err:
            exit_code = 1
            if args.json:
                results_out.append({"query": q, "error": err})
            else:
                print(f"[ERR] {err}", file=sys.stderr)
            continue

        assert res is not None
        if args.json:
            results_out.append(
                {
                    "query": res.query,
                    "lat": res.lat,
                    "lon": res.lon,
                    "display_name": res.display_name,
                    "importance": res.importance,
                }
            )
        else:
            if args.verbose:
                print(
                    f"{res.query} -> {res.lat:.8f}, {res.lon:.8f} | "
                    f"{res.display_name} (imp={res.importance:.3f})"
                )
            else:
                print(f"{res.query} -> {res.lat:.8f}, {res.lon:.8f}")

    save_cache(args.cache, cache)

    if args.json:
        print(json.dumps(results_out, indent=2, ensure_ascii=False))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
