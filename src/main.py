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
from datetime import date, time as dtime
from pathlib import Path

# Ensure src/ is on sys.path (consistent with your other CLIs)
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from geo.geocode_city import DEFAULT_CACHE, geocode, load_cache, save_cache
from civil_time.civil_time import resolve_local_to_utc, AmbiguousLocalTime, NonExistentLocalTime

# ASTRO modules live in src/astro/
from astro.zenith_constellation import constellation_at_zenith
from astro.sun_on_the_ecliptic import sun_on_the_ecliptic


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date '{s}'. Expected YYYY-MM-DD.") from e


def _parse_time(s: str) -> dtime:
    try:
        return dtime.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid time '{s}'. Expected HH:MM (or HH:MM:SS).") from e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GEO → TIME → ASTRO CLI; outputs one JSON object.")
    p.add_argument("-c", "--city", required=True, help='Place query, e.g. "Cosenza, Italy"')
    p.add_argument("-d", "--date", required=True, type=_parse_date, help="Local date YYYY-MM-DD")
    p.add_argument("-t", "--time", required=True, type=_parse_time, help="Local time HH:MM (or HH:MM:SS)")

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

    tzid = geo_res.tzname

    # -------------------------
    # TIME
    # -------------------------
    try:
        rr = resolve_local_to_utc(args.date, args.time, tzid, ambiguous="raise", nonexistent="raise")
    except AmbiguousLocalTime:
        warnings.append(f"Ambiguous local time in {tzid}; using policy ambiguous='{args.ambiguous}'.")
        rr = resolve_local_to_utc(args.date, args.time, tzid, ambiguous=args.ambiguous, nonexistent="raise")
    except NonExistentLocalTime:
        warnings.append(f"Non-existent local time in {tzid}; using policy nonexistent='{args.nonexistent}'.")
        rr = resolve_local_to_utc(args.date, args.time, tzid, ambiguous="raise", nonexistent=args.nonexistent)

    # For astropy Time(format='isot'), seconds are safest.
    utc_iso_for_astro = rr.utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # -------------------------
    # ASTRO
    # -------------------------
    astro_block: dict[str, object] = {}

    # Zenith constellation depends on (UTC, lat, lon)
    astro_block["zenith_constellation"] = constellation_at_zenith(
        utc_iso=utc_iso_for_astro,
        lat_deg=float(geo_res.lat),
        lon_deg=float(geo_res.lon),
        short=bool(args.short_constellation),
    )

    # Sun info depends only on UTC
    sun_ecl = sun_on_the_ecliptic(utc_iso_for_astro)
    sun_const = sun_ecl.constellation_short if args.short_constellation else sun_ecl.constellation
    astro_block["sun"] = {
        "constellation": sun_const,
        "ecliptic": {"lon_deg": sun_ecl.lon_deg, "lat_deg": sun_ecl.lat_deg},
        "icrs": {"ra_deg": sun_ecl.ra_deg, "dec_deg": sun_ecl.dec_deg},
    }

    # -------------------------
    # JSON output
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
        "time": {"local": local_iso, "utc": utc_iso, "warnings": warnings},
        "astro": astro_block,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
