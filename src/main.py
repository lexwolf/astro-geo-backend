#!/usr/bin/env python3
"""
src/main.py

GEO → TIME → ASTRO CLI that prints a single JSON object.

Inputs:
  --city  (place query)
  --date  (local date YYYY-MM-DD)
  --time  (local time HH:MM or HH:MM:SS)

Pipeline:
  GEO   : city -> {display_name, lat, lon, tzid}
  TIME  : local datetime + tzid -> UTC (with explicit DST handling + warnings)
  ASTRO : (a) IAU constellation at zenith for (lat,lon,UTC)
          (b) Sun constellation at UTC
          (c) Sun ecliptic lon/lat + ICRS ra/dec at UTC

Example:
  python3 src/main.py --city "Cosenza" --date 1982-08-25 --time 12:00
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path (consistent with your other CLIs)
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astrogeo_pipeline import (
    DEFAULT_CACHE,
    AstroGeoError,
    argparse_date,
    argparse_time,
    build_astrogeo_payload,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GEO → TIME → ASTRO CLI; outputs one JSON object.")
    p.add_argument("-c", "--city", required=True, help='Place query, e.g. "Cosenza, Italy"')
    p.add_argument("-d", "--date", required=True, type=argparse_date, help="Local date YYYY-MM-DD")
    p.add_argument("-t", "--time", required=True, type=argparse_time, help="Local time HH:MM (or HH:MM:SS)")

    # GEO cache / rate limiting
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Cache file path")
    p.add_argument("--min-delay", type=float, default=1.0, help="Min seconds between Nominatim API calls")

    # DST policies (used only after a strict attempt fails)
    p.add_argument("--ambiguous", choices=["earliest", "latest"], default="earliest")
    p.add_argument("--nonexistent", choices=["shift_forward", "shift_backward"], default="shift_forward")

    # ASTRO
    p.add_argument(
        "--short-constellation",
        action="store_true",
        help="Use 3-letter IAU constellation abbreviations (zenith + Sun).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_astrogeo_payload(
            args.city,
            args.date.isoformat(),
            args.time.isoformat(),
            cache_path=args.cache,
            min_delay_s=args.min_delay,
            ambiguous=args.ambiguous,
            nonexistent=args.nonexistent,
            short_constellation=bool(args.short_constellation),
        )
    except AstroGeoError as e:
        print(f"[ERR] {e.message}", file=sys.stderr)
        return {"GEOCODING_FAILED": 2, "TIMEZONE_FAILED": 3, "ASTRO_FAILED": 4}.get(e.code, 2)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
