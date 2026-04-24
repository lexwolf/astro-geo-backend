import json
import subprocess

import astrogeo_http


def test_validate_request_rejects_empty_city():
    status, payload, *_ = astrogeo_http.validate_request("", "1982-08-25", "12:00")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_CITY"
    assert payload["error"]["message"] == "City must be a non-empty string."


def test_validate_request_rejects_bad_date_without_backend_call():
    status, payload, *_ = astrogeo_http.validate_request("Cosenza", "1982-99-25", "12:00")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Invalid date '1982-99-25'. Expected YYYY-MM-DD."


def test_validate_request_rejects_bad_time_without_backend_call():
    status, payload, *_ = astrogeo_http.validate_request("Cosenza", "1982-08-25", "25:99")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_TIME"
    assert payload["error"]["message"] == "Invalid time '25:99'. Expected HH:MM or HH:MM:SS."


def test_run_backend_preserves_success_json(monkeypatch):
    expected = {"place": {}, "time": {}, "astro": {}}

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=json.dumps(expected), stderr="")

    monkeypatch.setattr(astrogeo_http.subprocess, "run", fake_run)

    status, payload = astrogeo_http.run_backend("python", "main.py", "Cosenza", "1982-08-25", "12:00")

    assert status == 200
    assert payload == expected


def test_run_backend_maps_geocoding_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            2,
            stdout="",
            stderr="[ERR] No results for 'Cosnzza'. Try adding country/region.",
        )

    monkeypatch.setattr(astrogeo_http.subprocess, "run", fake_run)

    status, payload = astrogeo_http.run_backend("python", "main.py", "Cosnzza", "1982-08-25", "12:00")

    assert status == 404
    assert payload["ok"] is False
    assert payload["error"]["code"] == "GEOCODING_FAILED"
    assert payload["error"]["message"] == "Could not resolve city 'Cosnzza'. Try adding country/region."
