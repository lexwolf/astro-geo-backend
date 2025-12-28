from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import (
    get_sun,
    get_constellation,
    GeocentricTrueEcliptic,
)


@dataclass(frozen=True)
class SunEcliptic:
    """
    Apparent geocentric position of the Sun.

    All angles are in degrees.
    """
    lon_deg: float   # ecliptic longitude (0–360)
    lat_deg: float   # ecliptic latitude (≈ 0)
    ra_deg: float    # right ascension
    dec_deg: float   # declination


def sun_on_the_ecliptic(utc_iso: str) -> SunEcliptic:
    """
    Compute the Sun's apparent position in the true ecliptic of date.

    Parameters
    ----------
    utc_iso : str
        UTC timestamp in ISO 8601 format (unambiguous).

    Returns
    -------
    SunEcliptic
        Ecliptic longitude/latitude and equatorial RA/Dec in degrees.
    """
    t = Time(utc_iso, format="isot", scale="utc")

    # Apparent geocentric Sun position
    sun = get_sun(t)
    sun_icrs = sun.icrs

    # Transform to true ecliptic of date
    ecl = sun.transform_to(GeocentricTrueEcliptic(obstime=t))

    lon = float(ecl.lon.wrap_at(360 * u.deg).deg)
    if lon < 0.0:
        lon += 360.0

    return SunEcliptic(
        lon_deg=lon,
        lat_deg=float(ecl.lat.deg),
        ra_deg=float(sun_icrs.ra.deg),
        dec_deg=float(sun_icrs.dec.deg),
    )


def sun_constellation(utc_iso: str, short: bool = False) -> str:
    """
    Return the IAU constellation in which the Sun is located
    at the given UTC time.

    Uses official IAU 88 constellation boundaries.

    Parameters
    ----------
    utc_iso : str
        UTC timestamp in ISO 8601 format.
    short : bool
        If True, return the 3-letter IAU abbreviation.

    Returns
    -------
    str
        Constellation name or abbreviation.
    """
    t = Time(utc_iso, format="isot", scale="utc")
    sun = get_sun(t).icrs
    return get_constellation(sun, short_name=short)
