#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, SkyCoord, get_constellation


@dataclass(frozen=True)
class ZenithResult:
    constellation: str
    abbrev: str
    ra_deg: float
    dec_deg: float


def constellation_at_zenith(
    utc_iso: str,
    lat_deg: float,
    lon_deg: float,
    short: bool = False,
) -> str:
    """
    Return the IAU constellation at the observer's zenith.

    Inputs are assumed already validated and unambiguous upstream.
    - utc_iso: ISO 8601 UTC timestamp (e.g. "2025-12-27T12:34:56Z")
    - lat_deg, lon_deg: observer latitude/longitude in degrees

    Output:
    - Full IAU constellation name by default
    - If short=True, returns the 3-letter IAU abbreviation
    """
    t = Time(utc_iso, format="isot", scale="utc")
    loc = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg)

    # Zenith in local horizontal coordinates.
    # az is arbitrary at zenith; we keep 0° for determinism.
    zen_altaz = SkyCoord(
        alt=90.0 * u.deg,
        az=0.0 * u.deg,
        frame=AltAz(obstime=t, location=loc),
    )

    # Transform to ICRS for constellation lookup
    zen_icrs = zen_altaz.icrs

    name = get_constellation(zen_icrs, short_name=False)
    abbr = get_constellation(zen_icrs, short_name=True)

    return abbr if short else name


def zenith_debug(
    utc_iso: str,
    lat_deg: float,
    lon_deg: float,
) -> ZenithResult:
    """Same computation, but also returns RA/Dec for debugging/logging."""
    t = Time(utc_iso, format="isot", scale="utc")
    loc = EarthLocation(lat=lat_deg * u.deg, lon=lon_deg * u.deg)

    zen_altaz = SkyCoord(
        alt=90.0 * u.deg,
        az=0.0 * u.deg,
        frame=AltAz(obstime=t, location=loc),
    )
    zen_icrs = zen_altaz.icrs

    name = get_constellation(zen_icrs, short_name=False)
    abbr = get_constellation(zen_icrs, short_name=True)

    return ZenithResult(
        constellation=name,
        abbrev=abbr,
        ra_deg=float(zen_icrs.ra.deg),
        dec_deg=float(zen_icrs.dec.deg),
    )
