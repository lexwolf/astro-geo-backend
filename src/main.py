#!/usr/bin/env python3
"""
src/main.py

CLI that:
  - accepts: city, date, time
  - GEO: geocode city -> (display_name, lat, lon, tzname)
  - TIME: resolve (local date+time, tzname) -> UTC
  - ASTRO: constellation at zenith (IAU) using UTC + lat/lon
  - prints a single JSON object

Examples (from repo root):
  python3 src/main.py --city "Cosenza, Italy" --date 1985-03-12 --time 08:30
  python3 src/main.py -c "Parma" -d 1985-03-12 -t 08:30

Notes:
  - If timezonefinder is not installed, tzname may be None -> we error out
  - DST ambiguity / gaps:
      we first try strict ("raise"); if it fails, we apply policies and add warnings.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, time as dtime
from pathlib import Path


# -----------------------------
# Ensure project root (src/) is on sys.path, like your other CLIs
# -----------------------------
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# -----------------------------
# Project imports
# -----------------------------
from geo.geocode_city import (
    DEFAULT_CACHE,
    geocode,
    load_cache,
    save_cache,
)
from civil_time.civil_time import (
    resolve_local_to_utc,
    AmbiguousLocalTime,
    NonExistentLocalTime,
)

# ASTRO: constellation at zenith
try:
    # If you place the module under src/astro/zenith_constellation.py
    from astro.zenith_constellation import constellation_at_zenith
except Exception:
    # If you place the module directly under src/zenith_constellation.py
    from zenith_constellation import constellation_at_zenith


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date '{s}'. Expected YYYY-MM-DD.") from e


def _parse_time(s: str) -> dtime:
    try:
        # accepts HH:MM or HH:MM:SS
        return dtime.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid time '{s}'. Expected HH:MM (or HH:MM:SS).") from e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GEO → TIME → ASTRO CLI; outputs one JSON object.")
    p.add_argument("-c", "--city", required=True, help='Place query, e.g. "Cosenza, Italy"')
    p.add_argument("-d", "--date", required=True, type=_parse_date, help="Local date YYYY-MM-DD")
    p.add_argument("-t", "--time", required=True, type=_parse_time, help="Local time HH:MM (or HH:MM:SS)")

    # Cache / rate-limit knobs consistent with your GEO CLIs
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Cache file path")
    p.add_argument("--min-delay", type=float, default=1.0, help="Min seconds between Nominatim API calls")

    # DST policies (used only if strict resolution fails)
    p.add_argument(
        "--ambiguous",
        choices=["earliest", "latest"],
        default="earliest",
        help="Policy if local time is ambiguous (DST fall-back). Used only after strict failure.",
    )
    p.add_argument(
        "--nonexistent",
        choices=["shift_forward", "shift_backward"],
        default="shift_forward",
        help="Policy if local time is non-existent (DST spring-forward gap). Used only after strict failure.",
    )

    # ASTRO options
    p.add_argument(
        "--short-constellation",
        action="store_true",
        help="Return 3-letter IAU constellation abbreviation instead of full name.",
    )

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    warnings: list[str] = []

    # -------------------------
    # GEO
    # -------------------------
    user_agent = "astro-geo-backend/0.1 (Alessandro Veltri; contact: alessandro.veltri@gmail.com)"

    cache = load_cache(args.cache)
    last_t = None

    geo_res, last_t, err = geocode(
        args.city,
        user_agent=user_agent,
        cache=cache,
        min_delay_s=args.min_delay,
        last_request_time=last_t,
        limit=1,
    )

    save_cache(args.cache, cache)

    if err or geo_res is None:
        print(f"[ERR] {err or 'Unknown geocoding error.'}", file=sys.stderr)
        return 2

    if geo_res.tzname is None:
        print(
            "[ERR] Timezone could not be resolved from coordinates.\n"
            "      Install 'timezonefinder' so GEO can return an IANA tzname.",
            file=sys.stderr,
        )
        return 3

    # -------------------------
    # TIME (strict first, then policy + warnings)
    # -------------------------
    tzid = geo_res.tzname

    try:
        rr = resolve_local_to_utc(args.date, args.time, tzid, ambiguous="raise", nonexistent="raise")
    except AmbiguousLocalTime:
        warnings.append(f"Ambiguous local time in {tzid}; using policy ambiguous='{args.ambiguous}'.")
        rr = resolve_local_to_utc(args.date, args.time, tzid, ambiguous=args.ambiguous, nonexistent="raise")
    except NonExistentLocalTime:
        warnings.append(f"Non-existent local time in {tzid}; using policy nonexistent='{args.nonexistent}'.")
        rr = resolve_local_to_utc(args.date, args.time, tzid, ambiguous="raise", nonexistent=args.nonexistent)

    # -------------------------
    # ASTRO (constellation at zenith)
    # -------------------------
    # Keep JSON formatting stable (minutes), but feed ASTRO a fully ISO '...:SSZ' string.
    utc_iso_for_astro = rr.utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        constell = constellation_at_zenith(
            utc_iso=utc_iso_for_astro,
            lat_deg=float(geo_res.lat),
            lon_deg=float(geo_res.lon),
            short=bool(args.short_constellation),
        )
    except Exception as e:
        # Don't crash the whole pipeline: record a warning and omit astro field.
        warnings.append(f"ASTRO failed: {e!r}")
        constell = None

    # -------------------------
    # JSON output (single object)
    # -------------------------
    local_iso = f"{args.date.isoformat()}T{args.time.strftime('%H:%M')}"
    utc_iso = rr.utc.strftime("%Y-%m-%dT%H:%MZ")

    payload: dict[str, object] = {
        "place": {
            "display_name": geo_res.display_name,
            "lat": float(geo_res.lat),
            "lon": float(geo_res.lon),
            "tzid": tzid,
        },
        "time": {
            "local": local_iso,
            "utc": utc_iso,
            "warnings": warnings,
        },
    }

    if constell is not None:
        payload["astro"] = {
            "zenith_constellation": constell,
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
