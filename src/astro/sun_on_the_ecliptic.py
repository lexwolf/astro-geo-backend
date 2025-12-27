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
    lon_deg: float
    lat_deg: float
    ra_deg: float
    dec_deg: float


def sun_on_the_ecliptic(utc_iso: str) -> SunEcliptic:
    t = Time(utc_iso, format="isot", scale="utc")

    sun = get_sun(t)
    sun_icrs = sun.icrs
    ecl = sun.transform_to(GeocentricTrueEcliptic(obstime=t))

    lon = float(ecl.lon.wrap_at(360 * u.deg).deg)
    if lon < 0:
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

    This uses official IAU 88 constellation boundaries.
    """
    t = Time(utc_iso, format="isot", scale="utc")
    sun = get_sun(t).icrs
    return get_constellation(sun, short_name=short)
