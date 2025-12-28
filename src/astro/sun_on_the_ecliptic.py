from __future__ import annotations

from dataclasses import dataclass

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import get_constellation, get_sun, GeocentricTrueEcliptic


@dataclass(frozen=True)
class SunEcliptic:
    lon_deg: float
    lat_deg: float
    ra_deg: float
    dec_deg: float
    constellation: str
    constellation_short: str


def sun_on_the_ecliptic(utc_iso: str) -> SunEcliptic:
    t = Time(utc_iso, format="isot", scale="utc")

    sun = get_sun(t)
    sun_icrs = sun.icrs
    ecl = sun.transform_to(GeocentricTrueEcliptic(obstime=t))

    lon = float(ecl.lon.wrap_at(360 * u.deg).deg)
    if lon < 0:
        lon += 360.0

    const_full = get_constellation(sun_icrs, short_name=False)
    const_short = get_constellation(sun_icrs, short_name=True)

    return SunEcliptic(
        lon_deg=lon,
        lat_deg=float(ecl.lat.deg),
        ra_deg=float(sun_icrs.ra.deg),
        dec_deg=float(sun_icrs.dec.deg),
        constellation=const_full,
        constellation_short=const_short,
    )


def sun_constellation(utc_iso: str, short: bool = False) -> str:
    """
    Return the IAU constellation in which the Sun is located
    at the given UTC time.

    This uses official IAU 88 constellation boundaries.
    """
    sun_ecl = sun_on_the_ecliptic(utc_iso)
    return sun_ecl.constellation_short if short else sun_ecl.constellation
