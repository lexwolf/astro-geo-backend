# tests/test_geocode_city_integration.py
"""
Integration tests for geo.geocode_city that hit the real Nominatim service.

These are **opt-in** tests:
- They are marked as "integration"
- They are skipped unless you set: RUN_INTEGRATION_TESTS=1

Run:
  RUN_INTEGRATION_TESTS=1 pytest -m integration -q
"""

import os
import time

import pytest

from geo.geocode_city import geocode

pytestmark = pytest.mark.integration


def _run_enabled() -> bool:
    return os.environ.get("RUN_INTEGRATION_TESTS", "").strip() in {"1", "true", "yes", "on"}


@pytest.mark.skipif(not _run_enabled(), reason="Set RUN_INTEGRATION_TESTS=1 to enable integration tests.")
def test_real_nominatim_geocode_single_query():
    # Use a realistic UA; Nominatim expects one identifying your app.
    ua = "astro-geo-backend-tests/0.1 (integration; contact: none)"

    res, last_t, err = geocode(
        "Cosenza, Italy",
        user_agent=ua,
        cache={},
        min_delay_s=1.0,
        last_request_time=None,
        limit=1,
    )

    assert err is None
    assert res is not None

    # Loose assertions: avoid failing due to minor geocoder changes.
    assert 38.5 < res.lat < 40.5
    assert 15.0 < res.lon < 18.0
    assert isinstance(res.display_name, str) and len(res.display_name) > 0


@pytest.mark.skipif(not _run_enabled(), reason="Set RUN_INTEGRATION_TESTS=1 to enable integration tests.")
def test_real_nominatim_rate_limit_is_respected():
    ua = "astro-geo-backend-tests/0.1 (integration; contact: none)"
    cache = {}
    last_t = None

    t0 = time.time()
    res1, last_t, err1 = geocode(
        "Quito, Ecuador",
        user_agent=ua,
        cache=cache,
        min_delay_s=1.0,
        last_request_time=last_t,
        limit=1,
    )
    assert err1 is None and res1 is not None

    # Second call should sleep (approximately) to respect min_delay_s (since cache is empty)
    res2, last_t, err2 = geocode(
        "Cosenza, Italy",
        user_agent=ua,
        cache=cache,
        min_delay_s=1.0,
        last_request_time=last_t,
        limit=1,
    )
    t1 = time.time()

    assert err2 is None and res2 is not None
    assert (t1 - t0) >= 1.0 - 0.05  # allow small scheduling jitter


@pytest.mark.skipif(not _run_enabled(), reason="Set RUN_INTEGRATION_TESTS=1 to enable integration tests.")
def test_real_nominatim_cache_prevents_second_network_call(monkeypatch):
    """
    First call fills cache; second call should return from cache and not touch the network.
    We enforce that by patching _http_get_json to explode after the first call.
    """
    ua = "astro-geo-backend-tests/0.1 (integration; contact: none)"
    cache = {}
    last_t = None

    res1, last_t, err1 = geocode(
        "Cosenza, Italy",
        user_agent=ua,
        cache=cache,
        min_delay_s=1.0,
        last_request_time=last_t,
        limit=1,
    )
    assert err1 is None and res1 is not None
    assert "Cosenza, Italy" in cache  # normalized key

    # Now ensure any HTTP would fail if it were attempted
    def boom(*args, **kwargs):
        raise RuntimeError("Network should not be called on cache hit.")

    monkeypatch.setattr("geo.geocode_city.http_get_json", boom)

    res2, last_t2, err2 = geocode(
        "Cosenza, Italy",
        user_agent=ua,
        cache=cache,
        min_delay_s=1.0,
        last_request_time=last_t,
        limit=1,
    )

    assert err2 is None
    assert res2 is not None
    assert res2.lat == res1.lat
    assert res2.lon == res1.lon
