import asyncio
import json
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

import api
import astrogeo_pipeline
from geo.geocode_city import GeoResult


def _run_app(path="/astrogeo/v1/astrogeo", params=None, method="GET"):
    messages = []
    query_string = urlencode(params or {}).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string,
    }
    asyncio.run(api.app(scope, receive, send))

    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    headers = {k.decode("ascii").lower(): v.decode("ascii") for k, v in start["headers"]}
    return start["status"], headers, json.loads(body.decode("utf-8"))


@pytest.fixture(autouse=True)
def no_cache_io(monkeypatch):
    monkeypatch.setattr(astrogeo_pipeline, "load_cache", lambda path: {})
    monkeypatch.setattr(astrogeo_pipeline, "save_cache", lambda path, cache: None)


@pytest.fixture
def fake_astro(monkeypatch):
    monkeypatch.setattr(astrogeo_pipeline, "constellation_at_zenith", lambda **kwargs: "Virgo")
    monkeypatch.setattr(
        astrogeo_pipeline,
        "sun_on_the_ecliptic",
        lambda utc_iso: SimpleNamespace(lon_deg=152.0, lat_deg=0.0, ra_deg=150.0, dec_deg=12.0),
    )
    monkeypatch.setattr(astrogeo_pipeline, "sun_constellation", lambda utc_iso, short=False: "Leo")


def test_valid_request_returns_json_with_place_time_astro(monkeypatch, fake_astro):
    def fake_geocode(*args, **kwargs):
        return (
            GeoResult(
                query="Cosenza",
                lat=39.298262,
                lon=16.253735,
                display_name="Cosenza, Calabria, Italia",
                importance=0.45,
                tzname="Europe/Rome",
            ),
            None,
            None,
        )

    monkeypatch.setattr(astrogeo_pipeline, "geocode", fake_geocode)

    status, headers, payload = _run_app(
        params={"city": "Cosenza", "date": "1982-08-25", "time": "12:00"}
    )

    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert set(payload) == {"place", "time", "astro"}
    assert payload["time"]["warnings"] == []


@pytest.mark.parametrize("date_s", ["0100-08-25", "0050-08-25", "0001-08-25"])
def test_ancient_zero_padded_dates_return_json_with_warning(monkeypatch, fake_astro, date_s):
    def fake_geocode(*args, **kwargs):
        return (
            GeoResult(
                query="Cosenza",
                lat=39.298262,
                lon=16.253735,
                display_name="Cosenza, Calabria, Italia",
                importance=0.45,
                tzname="UTC",
            ),
            None,
            None,
        )

    monkeypatch.setattr(astrogeo_pipeline, "geocode", fake_geocode)

    status, headers, payload = _run_app(
        params={"city": "Cosenza", "date": date_s, "time": "12:00"}
    )

    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert set(payload) == {"place", "time", "astro"}
    assert payload["time"]["local"] == f"{date_s}T12:00"
    assert any("proleptic Gregorian" in warning for warning in payload["time"]["warnings"])


def test_bad_city_returns_geocoding_failed_json(monkeypatch):
    def fake_geocode(*args, **kwargs):
        return None, None, "No results for 'Cosnzza'. Try adding country/region."

    monkeypatch.setattr(astrogeo_pipeline, "geocode", fake_geocode)

    status, headers, payload = _run_app(
        params={"city": "Cosnzza", "date": "1982-08-25", "time": "12:00"}
    )

    assert status == 404
    assert headers["content-type"].startswith("application/json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "GEOCODING_FAILED"
    assert payload["error"]["message"] == "Could not resolve city 'Cosnzza'. Try adding country/region."


def test_bad_date_returns_invalid_date_json(monkeypatch):
    monkeypatch.setattr(astrogeo_pipeline, "geocode", lambda *a, **k: pytest.fail("geocode called"))

    status, headers, payload = _run_app(
        params={"city": "Cosenza", "date": "1982-99-25", "time": "12:00"}
    )

    assert status == 400
    assert headers["content-type"].startswith("application/json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Invalid date '1982-99-25'. Expected YYYY-MM-DD with year 0001-9999."


@pytest.mark.parametrize("date_s", ["0000-08-25", "100-08-25", "50-08-25"])
def test_bad_ancient_date_forms_return_invalid_date_json(monkeypatch, date_s):
    monkeypatch.setattr(astrogeo_pipeline, "geocode", lambda *a, **k: pytest.fail("geocode called"))

    status, headers, payload = _run_app(
        params={"city": "Cosenza", "date": date_s, "time": "12:00"}
    )

    assert status == 400
    assert headers["content-type"].startswith("application/json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == f"Invalid date '{date_s}'. Expected YYYY-MM-DD with year 0001-9999."


def test_cli_bad_date_returns_structured_json():
    proc = subprocess.run(
        [
            sys.executable,
            "src/main.py",
            "--city",
            "Cosenza",
            "--date",
            "100-08-25",
            "--time",
            "12:00",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload == {
        "ok": False,
        "error": {
            "code": "INVALID_DATE",
            "message": "Invalid date '100-08-25'. Expected YYYY-MM-DD with year 0001-9999.",
        },
    }


def test_bad_time_returns_invalid_time_json(monkeypatch):
    monkeypatch.setattr(astrogeo_pipeline, "geocode", lambda *a, **k: pytest.fail("geocode called"))

    status, headers, payload = _run_app(
        params={"city": "Cosenza", "date": "1982-08-25", "time": "25:99"}
    )

    assert status == 400
    assert headers["content-type"].startswith("application/json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_TIME"
    assert payload["error"]["message"] == "Invalid time '25:99'. Expected HH:MM or HH:MM:SS."


@pytest.mark.parametrize("params", [{}, {"city": "", "date": "1982-08-25", "time": "12:00"}])
def test_missing_or_empty_city_returns_invalid_city_json(monkeypatch, params):
    monkeypatch.setattr(astrogeo_pipeline, "geocode", lambda *a, **k: pytest.fail("geocode called"))

    status, headers, payload = _run_app(params=params)

    assert status == 400
    assert headers["content-type"].startswith("application/json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_CITY"
    assert payload["error"]["message"] == "City must be a non-empty string."
