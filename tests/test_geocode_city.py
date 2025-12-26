import time
from pathlib import Path

import pytest

from geo.geocode_city import geocode, GeoResult


FAKE_RESPONSE = [
    {
        "lat": "39.298262",
        "lon": "16.253735",
        "display_name": "Cosenza, Calabria, Italia",
        "importance": 0.45,
    }
]


def test_cache_hit_no_http(monkeypatch):
    cache = {
        "Cosenza, Italy": {
            "lat": 39.298262,
            "lon": 16.253735,
            "display_name": "Cached Cosenza",
            "importance": 0.9,
        }
    }

    called = False

    def fake_http(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("geo.geocode_city.http_get_json", fake_http)

    res, last_t, err = geocode(
        "Cosenza, Italy",
        user_agent="test",
        cache=cache,
        min_delay_s=1.0,
        last_request_time=None,
    )

    assert err is None
    assert isinstance(res, GeoResult)
    assert res.lat == 39.298262
    assert called is False


def test_successful_http_call(monkeypatch):
    def fake_http(url, user_agent, timeout=15.0):
        return FAKE_RESPONSE

    monkeypatch.setattr("geo.geocode_city.http_get_json", fake_http)

    cache = {}
    res, last_t, err = geocode(
        "Cosenza, Italy",
        user_agent="test",
        cache=cache,
        min_delay_s=0.0,
        last_request_time=None,
    )

    assert err is None
    assert res is not None
    assert pytest.approx(res.lat) == 39.298262
    assert "Cosenza" in res.display_name
    assert "Cosenza, Italy" in cache


def test_no_results(monkeypatch):
    monkeypatch.setattr("geo.geocode_city.http_get_json", lambda *a, **k: [])

    res, last_t, err = geocode(
        "Nowhere City",
        user_agent="test",
        cache={},
        min_delay_s=0.0,
        last_request_time=None,
    )

    assert res is None
    assert err is not None
    assert "No results" in err


def test_network_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("geo.geocode_city.http_get_json", boom)

    res, last_t, err = geocode(
        "Cosenza, Italy",
        user_agent="test",
        cache={},
        min_delay_s=0.0,
        last_request_time=None,
    )

    assert res is None
    assert "Network/API error" in err
