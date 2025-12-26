# src/geo/geocode_city.py
"""
Geocode city/place names to coordinates using OpenStreetMap Nominatim.

Library module (no CLI). Use gimme_geocode_city.py for command-line usage.

Optional feature:
- If `timezonefinder` is installed, this module can also return an IANA tzname
  (e.g. "Europe/Rome") from the geocoded coordinates.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_CACHE = Path.home() / ".cache" / "geo_city_cache.json"


# -----------------------------
# Optional tzname lookup (lat/lon -> IANA tz)
# -----------------------------
_TF = None
try:
    # timezonefinder is optional; we degrade gracefully if absent.
    from timezonefinder import TimezoneFinder  # type: ignore

    _TF = TimezoneFinder()
except Exception:
    _TF = None


def tzname_from_coords(lat: float, lon: float) -> Optional[str]:
    """
    Return an IANA timezone name for WGS84 coordinates (lat, lon), or None.

    Requires optional dependency: timezonefinder
    """
    if _TF is None:
        return None
    try:
        tz = _TF.timezone_at(lng=lon, lat=lat)
        if tz is None:
            tz = _TF.certain_timezone_at(lng=lon, lat=lat)
        return tz
    except Exception:
        return None

# -----------------------------
# Data model
# -----------------------------
@dataclass(frozen=True)
class GeoResult:
    query: str
    lat: float
    lon: float
    display_name: str
    importance: float
    tzname: Optional[str] = None


# -----------------------------
# Cache helpers
# -----------------------------
def load_cache(path: Path = DEFAULT_CACHE) -> Dict[str, Dict[str, Any]]:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        # Cache corruption shouldn't kill the tool; just start fresh.
        return {}


def save_cache(path: Path, cache: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


# -----------------------------
# HTTP helper (mock seam for tests)
# -----------------------------
def http_get_json(url: str, user_agent: str, timeout: float = 15.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


# -----------------------------
# Main API
# -----------------------------
def geocode(
    query: str,
    *,
    user_agent: str,
    cache: Dict[str, Dict[str, Any]],
    min_delay_s: float = 1.0,
    last_request_time: Optional[float] = None,
    limit: int = 1,
) -> Tuple[Optional[GeoResult], Optional[float], Optional[str]]:
    """
    Resolve a place query to coordinates (+ optional tzname).

    Returns: (GeoResult|None, new_last_request_time|None, error|None)

    - If cached, no HTTP request is performed and last_request_time is returned unchanged.
    - If a network call is made, new_last_request_time is set to current time.
    - tzname is filled only if timezonefinder is installed; otherwise None.
    """
    norm = " ".join(query.strip().split())
    if not norm:
        return None, last_request_time, "Empty query."

    # Cache hit
    if norm in cache:
        c = cache[norm]
        try:
            lat = float(c["lat"])
            lon = float(c["lon"])
            tz_cached = c.get("tzname")
            tz = str(tz_cached) if tz_cached else None

            # Upgrade old cache entries (computed before timezonefinder was installed)
            if tz is None:
                tz = tzname_from_coords(lat, lon)
                if tz:
                    c["tzname"] = tz

            return (
                GeoResult(
                    query=norm,
                    lat=lat,
                    lon=lon,
                    display_name=str(c.get("display_name", "")),
                    importance=float(c.get("importance", 0.0)),
                    tzname=tz,
                ),
                last_request_time,
                None,
            )
        except Exception:
            cache.pop(norm, None)  # malformed cache entry -> refetch

    # Rate limiting (only before network calls)
    now = time.time()
    if last_request_time is not None:
        elapsed = now - last_request_time
        if elapsed < min_delay_s:
            time.sleep(min_delay_s - elapsed)

    params = {
        "q": norm,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": "0",
    }
    url = NOMINATIM_URL + "?" + urllib.parse.urlencode(params)

    try:
        data = http_get_json(url, user_agent=user_agent)
        new_last = time.time()
    except Exception as e:
        return None, last_request_time, f"Network/API error for '{norm}': {e}"

    if not isinstance(data, list) or len(data) == 0:
        return None, new_last, f"No results for '{norm}'. Try adding country/region."

    best = data[0]
    try:
        lat = float(best["lat"])
        lon = float(best["lon"])
        display_name = str(best.get("display_name", ""))
        importance = float(best.get("importance", 0.0))
    except Exception:
        return None, new_last, f"Unexpected API response shape for '{norm}'."

    tz = tzname_from_coords(lat, lon)

    res = GeoResult(
        query=norm,
        lat=lat,
        lon=lon,
        display_name=display_name,
        importance=importance,
        tzname=tz,
    )

    # Store to cache
    cache[norm] = {
        "lat": res.lat,
        "lon": res.lon,
        "display_name": res.display_name,
        "importance": res.importance,
        "tzname": res.tzname,
    }

    return res, new_last, None
