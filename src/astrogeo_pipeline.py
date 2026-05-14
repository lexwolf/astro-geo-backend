from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, time as dtime
from pathlib import Path
import re

from astro.sun_on_the_ecliptic import sun_constellation, sun_on_the_ecliptic
from astro.zenith_constellation import constellation_at_zenith
from civil_time.civil_time import AmbiguousLocalTime, NonExistentLocalTime, resolve_local_to_utc
from geo.geocode_city import DEFAULT_CACHE, geocode, load_cache, save_cache

USER_AGENT = "astro-geo-backend/0.1 (Alessandro Veltri; contact: alessandro.veltri@gmail.com)"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_EXPECTATION = "Expected YYYY-MM-DD with year 0001-9999."
HISTORICAL_DATE_WARNING = (
    "Dates outside the modern high-confidence range use a proleptic Gregorian calendar "
    "and approximate astronomical time models."
)


@dataclass(frozen=True)
class AstroGeoError(Exception):
    code: str
    message: str
    status_code: int

    def __str__(self) -> str:
        return self.message


def parse_date(date_s: str) -> date:
    if not DATE_RE.fullmatch(date_s):
        raise AstroGeoError(
            "INVALID_DATE",
            f"Invalid date '{date_s}'. {DATE_EXPECTATION}",
            400,
        )

    try:
        year = int(date_s[:4])
        month = int(date_s[5:7])
        day = int(date_s[8:10])
        if year == 0:
            raise ValueError("year 0 is out of range")
        return date(year, month, day)
    except ValueError as e:
        raise AstroGeoError(
            "INVALID_DATE",
            f"Invalid date '{date_s}'. {DATE_EXPECTATION}",
            400,
        ) from e


def parse_time(time_s: str) -> dtime:
    try:
        return dtime.fromisoformat(time_s)
    except ValueError as e:
        raise AstroGeoError(
            "INVALID_TIME",
            f"Invalid time '{time_s}'. Expected HH:MM or HH:MM:SS.",
            400,
        ) from e


def argparse_date(date_s: str) -> date:
    try:
        return parse_date(date_s)
    except AstroGeoError as e:
        raise argparse.ArgumentTypeError(e.message) from e


def argparse_time(time_s: str) -> dtime:
    try:
        return parse_time(time_s)
    except AstroGeoError as e:
        raise argparse.ArgumentTypeError(e.message) from e


def _validate_city(city: str | None) -> str:
    if not isinstance(city, str) or not city.strip():
        raise AstroGeoError("INVALID_CITY", "City must be a non-empty string.", 400)
    return " ".join(city.strip().split())


def _geocoding_message(city: str, err: str | None) -> str:
    suffix = "Try adding country/region."
    if err and suffix in err:
        return f"Could not resolve city '{city}'. {suffix}"
    return err or f"Could not resolve city '{city}'."


def build_astrogeo_payload(
    city: str,
    date_s: str,
    time_s: str,
    *,
    cache_path: Path = DEFAULT_CACHE,
    min_delay_s: float = 1.0,
    ambiguous: str = "earliest",
    nonexistent: str = "shift_forward",
    short_constellation: bool = False,
    user_agent: str = USER_AGENT,
) -> dict[str, object]:
    city_norm = _validate_city(city)
    local_date = parse_date(date_s)
    local_time = parse_time(time_s)
    warnings: list[str] = []
    if local_date.year < 1900 or local_date.year > 2100:
        warnings.append(HISTORICAL_DATE_WARNING)

    cache = load_cache(cache_path)
    geo_res, _last_t, err = geocode(
        city_norm,
        user_agent=user_agent,
        cache=cache,
        min_delay_s=min_delay_s,
        last_request_time=None,
        limit=1,
    )
    save_cache(cache_path, cache)

    if err or geo_res is None:
        raise AstroGeoError("GEOCODING_FAILED", _geocoding_message(city_norm, err), 404)

    if geo_res.tzname is None:
        raise AstroGeoError(
            "TIMEZONE_FAILED",
            "Timezone could not be resolved from coordinates.",
            500,
        )

    tzid = geo_res.tzname

    try:
        rr = resolve_local_to_utc(local_date, local_time, tzid, ambiguous="raise", nonexistent="raise")
    except AmbiguousLocalTime:
        warnings.append(f"Ambiguous local time in {tzid}; using policy ambiguous='{ambiguous}'.")
        rr = resolve_local_to_utc(local_date, local_time, tzid, ambiguous=ambiguous, nonexistent="raise")
    except NonExistentLocalTime:
        warnings.append(f"Non-existent local time in {tzid}; using policy nonexistent='{nonexistent}'.")
        rr = resolve_local_to_utc(local_date, local_time, tzid, ambiguous="raise", nonexistent=nonexistent)

    utc_iso_for_astro = f"{rr.utc.date().isoformat()}T{rr.utc.hour:02d}:{rr.utc.minute:02d}:{rr.utc.second:02d}Z"

    try:
        zenith_constellation = constellation_at_zenith(
            utc_iso=utc_iso_for_astro,
            lat_deg=float(geo_res.lat),
            lon_deg=float(geo_res.lon),
            short=bool(short_constellation),
        )
        sun_ecl = sun_on_the_ecliptic(utc_iso_for_astro)
        sun_const = sun_constellation(utc_iso_for_astro, short=bool(short_constellation))
    except Exception as e:
        raise AstroGeoError(
            "ASTRO_FAILED",
            "Astronomical context computation failed.",
            500,
        ) from e

    local_iso = f"{local_date.isoformat()}T{local_time.strftime('%H:%M')}"
    utc_iso = f"{rr.utc.date().isoformat()}T{rr.utc.hour:02d}:{rr.utc.minute:02d}Z"

    return {
        "place": {
            "display_name": geo_res.display_name,
            "lat": float(geo_res.lat),
            "lon": float(geo_res.lon),
            "tzid": tzid,
        },
        "time": {"local": local_iso, "utc": utc_iso, "warnings": warnings},
        "astro": {
            "zenith_constellation": zenith_constellation,
            "sun": {
                "constellation": sun_const,
                "ecliptic": {"lon_deg": sun_ecl.lon_deg, "lat_deg": sun_ecl.lat_deg},
                "icrs": {"ra_deg": sun_ecl.ra_deg, "dec_deg": sun_ecl.dec_deg},
            },
        },
    }
