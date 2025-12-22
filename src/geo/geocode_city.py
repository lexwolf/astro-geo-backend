#!/usr/bin/env python3
"""
Geocode city/place names to coordinates using OpenStreetMap Nominatim.

Usage:
  ./geocode_city.py "Cosenza, Italy"
  ./geocode_city.py "Quito, Ecuador" --json
  ./geocode_city.py --file cities.txt

Notes:
- Be polite: Nominatim requires a valid User-Agent and rate limiting.
- This script keeps a small JSON cache to reduce requests.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_CACHE = Path.home() / ".cache" / "geo_city_cache.json"


@dataclass(frozen=True)
class GeoResult:
    query: str
    lat: float
    lon: float
    display_name: str
    importance: float


def _load_cache(path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        # Cache corruption shouldn't kill the tool; just start fresh.
        return {}


def _save_cache(path: Path, cache: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _http_get_json(url: str, user_agent: str, timeout: float = 15.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset))


def geocode(
    query: str,
    *,
    user_agent: str,
    cache: Dict[str, Dict[str, Any]],
    min_delay_s: float,
    last_request_time: Optional[float],
    limit: int = 1,
) -> Tuple[Optional[GeoResult], Optional[float], Optional[str]]:
    """
    Returns: (GeoResult|None, new_last_request_time|None, error|None)
    """

    norm = " ".join(query.strip().split())
    if not norm:
        return None, last_request_time, "Empty query."

    # Cache hit
    if norm in cache:
        c = cache[norm]
        try:
            return (
                GeoResult(
                    query=norm,
                    lat=float(c["lat"]),
                    lon=float(c["lon"]),
                    display_name=str(c.get("display_name", "")),
                    importance=float(c.get("importance", 0.0)),
                ),
                last_request_time,
                None,
            )
        except Exception:
            # If cache entry is malformed, drop through to refetch.
            cache.pop(norm, None)

    # Rate limiting (only for network calls)
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
        data = _http_get_json(url, user_agent=user_agent)
        new_last = time.time()
    except Exception as e:
        return None, last_request_time, f"Network/API error for '{norm}': {e}"

    if not isinstance(data, list) or len(data) == 0:
        return None, new_last, f"No results for '{norm}'. Try adding country/region."

    best = data[0]
    try:
        res = GeoResult(
            query=norm,
            lat=float(best["lat"]),
            lon=float(best["lon"]),
            display_name=str(best.get("display_name", "")),
            importance=float(best.get("importance", 0.0)),
        )
    except Exception:
        return None, new_last, f"Unexpected API response shape for '{norm}'."

    # Store to cache
    cache[norm] = {
        "lat": res.lat,
        "lon": res.lon,
        "display_name": res.display_name,
        "importance": res.importance,
    }

    return res, new_last, None


def main() -> int:
    p = argparse.ArgumentParser(description="Geocode city/place names to coordinates.")
    p.add_argument("query", nargs="?", help="Place query, e.g. 'Cosenza, Italy'")
    p.add_argument("--file", type=Path, help="Read one query per line from a file.")
    p.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="Cache file path.")
    p.add_argument("--min-delay", type=float, default=1.0, help="Min seconds between API calls.")
    p.add_argument("--json", action="store_true", help="Print JSON output.")
    p.add_argument("--verbose", action="store_true", help="Print display_name and importance.")
    args = p.parse_args()

    # IMPORTANT: Use a real UA string identifying your app and a contact.
    # Replace with your project/app name.
    user_agent = "astro-geo-backend/0.1 (Alessandro Veltri; contact: alessandro.veltri@gmail.com)"

    cache = _load_cache(args.cache)
    last_t: Optional[float] = None

    queries = []
    if args.file:
        try:
            queries = [line.strip() for line in args.file.read_text(encoding="utf-8").splitlines()]
            queries = [q for q in queries if q and not q.startswith("#")]
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 2
    elif args.query:
        queries = [args.query]
    else:
        print("Provide a query string or --file.", file=sys.stderr)
        return 2

    results_out = []
    exit_code = 0

    for q in queries:
        res, last_t, err = geocode(
            q,
            user_agent=user_agent,
            cache=cache,
            min_delay_s=args.min_delay,
            last_request_time=last_t,
            limit=1,
        )
        if err:
            exit_code = 1
            if args.json:
                results_out.append({"query": q, "error": err})
            else:
                print(f"[ERR] {err}", file=sys.stderr)
            continue

        assert res is not None
        if args.json:
            results_out.append(
                {
                    "query": res.query,
                    "lat": res.lat,
                    "lon": res.lon,
                    "display_name": res.display_name,
                    "importance": res.importance,
                }
            )
        else:
            if args.verbose:
                print(f"{res.query} -> {res.lat:.8f}, {res.lon:.8f} | {res.display_name} (imp={res.importance:.3f})")
            else:
                print(f"{res.query} -> {res.lat:.8f}, {res.lon:.8f}")

    _save_cache(args.cache, cache)

    if args.json:
        print(json.dumps(results_out, indent=2, ensure_ascii=False))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
