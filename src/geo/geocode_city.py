from __future__ import annotations

import json
import urllib.parse
import urllib.request


class GeocodingError(RuntimeError):
    pass


def geocode_city(
    city_name: str,
    *,
    user_agent: str = "astro-geo-backend",
    timeout: float = 10.0,
) -> tuple[float, float]:
    if not city_name or not city_name.strip():
        raise ValueError("city_name must be a non-empty string")

    query = urllib.parse.urlencode({"format": "json", "q": city_name, "limit": 1})
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - network dependent
        raise GeocodingError("Failed to reach geocoding service") from exc

    try:
        results = json.loads(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - network dependent
        raise GeocodingError("Invalid geocoding response") from exc

    if not results:
        raise GeocodingError(f"No coordinates found for '{city_name}'")

    try:
        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("Unexpected geocoding response shape") from exc

    return lat, lon
