#!/usr/bin/env python3
import argparse

from astro.sun_on_the_ecliptic import sun_on_the_ecliptic, sun_constellation


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compute the Sun's ecliptic longitude at a given UTC timestamp."
    )
    ap.add_argument("--utc", required=True, help='UTC ISO 8601, e.g. "2025-12-27T12:00:00Z"')
    ap.add_argument("--short", action="store_true", help="Use 3-letter IAU constellation abbreviation")
    args = ap.parse_args()

    r = sun_on_the_ecliptic(args.utc)
    print(f"sun_ecl_lon_deg : {r.lon_deg:.6f}")
    print(f"sun_ecl_lat_deg : {r.lat_deg:.6f}")
    print(f"sun_ra_deg      : {r.ra_deg:.6f}")
    print(f"sun_dec_deg     : {r.dec_deg:.6f}")

    const = sun_constellation(args.utc, short=args.short)
    print(f"sun_const       : {const}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
