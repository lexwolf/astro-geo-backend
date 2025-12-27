#!/usr/bin/env python3
import argparse

from astro.zenith_constellation import constellation_at_zenith, sun_constellation


def main() -> int:
    ap = argparse.ArgumentParser(
        description="IAU constellation at zenith for a given UTC timestamp and observer location."
    )
    ap.add_argument("--utc", required=True, help="UTC timestamp in ISO 8601 (e.g. 2025-12-27T12:00:00Z)")
    ap.add_argument("--lat", type=float, required=True, help="Latitude in degrees")
    ap.add_argument("--lon", type=float, required=True, help="Longitude in degrees (east positive)")
    ap.add_argument("--short", action="store_true", help="Return IAU 3-letter abbreviation")
    args = ap.parse_args()

    print(constellation_at_zenith(args.utc, args.lat, args.lon, short=args.short))
    r = sun_on_the_ecliptic(args.utc)
    print(f"sun_ecl_lon_deg : {r.lon_deg:.6f}")
    print(f"sun_const      : {sun_constellation(args.utc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
