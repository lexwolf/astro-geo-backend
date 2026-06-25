import io
import json
import subprocess
from types import SimpleNamespace
from urllib.parse import urlparse

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
    assert payload["error"]["message"] == "Invalid date '1982-99-25'. Expected YYYY-MM-DD with year 0001-9999."


def test_validate_request_accepts_ancient_zero_padded_date():
    status, payload, city, date, time = astrogeo_http.validate_request("Cosenza", "0100-08-25", "12:00")

    assert status is None
    assert payload is None
    assert city == "Cosenza"
    assert date == "0100-08-25"
    assert time == "12:00"


def test_validate_request_accepts_eu_date_as_canonical_iso_date():
    status, payload, city, date, time = astrogeo_http.validate_request(
        "Cosenza", None, "12:00", eu_date="25-08-1982"
    )

    assert status is None
    assert payload is None
    assert city == "Cosenza"
    assert date == "1982-08-25"
    assert time == "12:00"


def test_validate_request_accepts_historical_eu_date_as_canonical_iso_date():
    status, payload, city, date, time = astrogeo_http.validate_request(
        "Cosenza", None, "12:00", eu_date="21-01-0100"
    )

    assert status is None
    assert payload is None
    assert city == "Cosenza"
    assert date == "0100-01-21"
    assert time == "12:00"


def test_validate_request_rejects_date_and_eu_date_together():
    status, payload, *_ = astrogeo_http.validate_request(
        "Cosenza", "1982-08-25", "12:00", eu_date="25-08-1982"
    )

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Provide either date=YYYY-MM-DD or eu_date=DD-MM-YYYY, not both."


def test_validate_request_rejects_missing_date_and_eu_date():
    status, payload, *_ = astrogeo_http.validate_request("Cosenza", None, "12:00")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Missing date. Provide either date=YYYY-MM-DD or eu_date=DD-MM-YYYY."


def test_validate_request_rejects_invalid_eu_date():
    status, payload, *_ = astrogeo_http.validate_request(
        "Cosenza", None, "12:00", eu_date="31-02-1982"
    )

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Invalid eu_date '31-02-1982'. Expected DD-MM-YYYY with year 0001-9999."


def test_validate_request_rejects_year_zero():
    status, payload, *_ = astrogeo_http.validate_request("Cosenza", "0000-08-25", "12:00")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Invalid date '0000-08-25'. Expected YYYY-MM-DD with year 0001-9999."


def test_validate_request_rejects_non_four_digit_year():
    status, payload, *_ = astrogeo_http.validate_request("Cosenza", "100-08-25", "12:00")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Invalid date '100-08-25'. Expected YYYY-MM-DD with year 0001-9999."


def test_validate_request_rejects_bad_time_without_backend_call():
    status, payload, *_ = astrogeo_http.validate_request("Cosenza", "1982-08-25", "25:99")

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_TIME"
    assert payload["error"]["message"] == "Invalid time '25:99'. Expected HH:MM or HH:MM:SS."


def test_validate_daily_reading_request_rejects_invalid_sign():
    status, payload, *_ = astrogeo_http.validate_daily_reading_request(
        "ophiuchus", "Messina", "2026-06-17", "12:00"
    )

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_SIGN"
    assert "Expected one of:" in payload["error"]["message"]


def test_validate_daily_reading_request_accepts_sign_case_insensitively():
    status, payload, sign, city, date, time, has_city, language = astrogeo_http.validate_daily_reading_request(
        "Aries", "Messina", "2026-06-17", "12:00"
    )

    assert status is None
    assert payload is None
    assert sign == "aries"
    assert city == "Messina"
    assert date == "2026-06-17"
    assert time == "12:00"
    assert has_city is True
    assert language == "en"


def test_validate_daily_reading_request_accepts_eu_date_as_canonical_iso_date():
    status, payload, sign, city, date, time, has_city, language = astrogeo_http.validate_daily_reading_request(
        "aries", "Messina", None, "12:00", eu_date="17-06-2026"
    )

    assert status is None
    assert payload is None
    assert sign == "aries"
    assert city == "Messina"
    assert date == "2026-06-17"
    assert time == "12:00"
    assert has_city is True
    assert language == "en"


def test_validate_daily_reading_request_accepts_missing_city():
    status, payload, sign, city, date, time, has_city, language = astrogeo_http.validate_daily_reading_request(
        "aries", None, "2026-06-17", "12:00"
    )

    assert status is None
    assert payload is None
    assert sign == "aries"
    assert city == ""
    assert date == "2026-06-17"
    assert time == "12:00"
    assert has_city is False
    assert language == "en"


def test_validate_daily_reading_request_accepts_empty_city():
    status, payload, sign, city, date, time, has_city, language = astrogeo_http.validate_daily_reading_request(
        "aries", "   ", "2026-06-17", "12:00"
    )

    assert status is None
    assert payload is None
    assert sign == "aries"
    assert city == ""
    assert date == "2026-06-17"
    assert time == "12:00"
    assert has_city is False
    assert language == "en"


def test_validate_daily_reading_language_fallbacks_and_supported_values():
    assert astrogeo_http.validate_daily_reading_language(None) == "en"
    assert astrogeo_http.validate_daily_reading_language("") == "en"
    assert astrogeo_http.validate_daily_reading_language("de") == "en"
    assert astrogeo_http.validate_daily_reading_language("it") == "it"
    assert astrogeo_http.validate_daily_reading_language(" es ") == "es"


def test_validate_daily_reading_request_rejects_date_and_eu_date_together():
    status, payload, *_ = astrogeo_http.validate_daily_reading_request(
        "aries", "Messina", "2026-06-17", "12:00", eu_date="17-06-2026"
    )

    assert status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DATE"
    assert payload["error"]["message"] == "Provide either date=YYYY-MM-DD or eu_date=DD-MM-YYYY, not both."


def test_daily_reading_prefixed_path_is_registered():
    parsed = urlparse("/astrogeo/daily-reading?sign=aries&city=Messina&eu_date=17-06-2026&time=12:00")

    assert parsed.path in astrogeo_http.DAILY_READING_PATHS


def test_daily_reading_versioned_paths_are_registered():
    assert "/v1/daily-reading" in astrogeo_http.DAILY_READING_PATHS
    assert "/astrogeo/v1/daily-reading" in astrogeo_http.DAILY_READING_PATHS


class FakePostHandler:
    def __init__(self, path, body):
        self.path = path
        self.body = body
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.server = SimpleNamespace(venv_python="python", main_py="main.py")
        self.status = None
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name.lower()] = value

    def end_headers(self):
        pass


def _post(path, payload):
    handler = FakePostHandler(path, json.dumps(payload).encode("utf-8"))
    astrogeo_http.Handler.do_POST(handler)
    response = json.loads(handler.wfile.getvalue().decode("utf-8"))
    return handler.status, handler.response_headers, response


class FakeGetHandler(FakePostHandler):
    def __init__(self, path):
        super().__init__(path, b"")


def _get(path):
    handler = FakeGetHandler(path)
    astrogeo_http.Handler.do_GET(handler)
    response = json.loads(handler.wfile.getvalue().decode("utf-8"))
    return handler.status, handler.response_headers, response


def test_daily_reading_post_json_accepts_eu_date(monkeypatch):
    backend_payload = {
        "place": {"display_name": "Messina, Sicily, Italy"},
        "time": {"local": "2026-06-23T12:00"},
        "astro": {
            "zenith_constellation": "Aquila",
            "sun": {"constellation": "Gemini"},
        },
    }
    captured = {}

    def fake_run_backend(venv_python, main_py, city, date, time, **kwargs):
        captured.update({"city": city, "date": date, "time": time, "kwargs": kwargs})
        return 200, backend_payload

    def fake_generate_daily_reading(payload, model, ollama_url):
        captured["reading_payload"] = payload
        return {"kind": "daily_reading", "model": model, "text": "A playful line."}

    monkeypatch.setattr(astrogeo_http, "run_backend", fake_run_backend)
    monkeypatch.setattr(astrogeo_http, "generate_daily_reading", fake_generate_daily_reading)

    status, headers, payload = _post(
        "/astrogeo/daily-reading",
        {"sign": "aries", "city": "Messina", "eu_date": "23-06-2026", "time": "12:00", "language": "it"},
    )

    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert {key: captured[key] for key in ("city", "date", "time", "kwargs")} == {
        "city": "Messina",
        "date": "2026-06-23",
        "time": "12:00",
        "kwargs": {},
    }
    assert captured["reading_payload"]["has_city"] is True
    assert captured["reading_payload"]["language"] == "it"
    assert payload["daily_reading"]["text"] == "A playful line."


def test_daily_reading_post_json_rejects_invalid_sign_without_backend(monkeypatch):
    def fail_run_backend(*args, **kwargs):
        raise AssertionError("run_backend should not be called")

    monkeypatch.setattr(astrogeo_http, "run_backend", fail_run_backend)

    status, headers, payload = _post(
        "/astrogeo/v1/daily-reading",
        {"sign": "ophiuchus", "city": "Messina", "date": "2026-06-23", "time": "12:00"},
    )

    assert status == 400
    assert headers["content-type"].startswith("application/json")
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_SIGN"


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


def test_build_daily_reading_payload_uses_local_ollama_only(monkeypatch):
    backend_payload = {
        "place": {"display_name": "Messina, Sicily, Italy"},
        "time": {"local": "2026-06-17T12:00", "utc": "2026-06-17T10:00Z"},
        "astro": {
            "zenith_constellation": "Aquila",
            "sun": {"constellation": "Gemini"},
        },
    }
    captured = {}

    def fake_generate_daily_reading(payload, model, ollama_url):
        captured["payload"] = payload
        captured["model"] = model
        captured["ollama_url"] = ollama_url
        return {
            "kind": "daily_reading",
            "model": model,
            "disclaimer": "Entertainment text generated from astronomical context; not a scientific prediction.",
            "text": "A playful line.",
        }

    monkeypatch.setattr(astrogeo_http, "generate_daily_reading", fake_generate_daily_reading)

    status, payload = astrogeo_http.build_daily_reading_payload(
        "aries", "Messina", "2026-06-17", backend_payload
    )

    assert status == 200
    assert payload["place"] == backend_payload["place"]
    assert payload["time"] == backend_payload["time"]
    assert payload["astro"] == {
        "sun_constellation": "Gemini",
        "zenith_constellation": "Aquila",
    }
    assert payload["daily_reading"]["text"] == "A playful line."
    assert captured["payload"] == {
        "sign": "aries",
        "local_date": "2026-06-17",
        "city": "Messina, Sicily, Italy",
        "has_city": True,
        "language": "en",
        "sun_constellation": "Gemini",
        "zenith_constellation": "Aquila",
    }
    assert captured["model"] == "llama3.2:3b"
    assert captured["ollama_url"] == "http://127.0.0.1:11434/api/generate"


def test_build_daily_reading_payload_maps_ollama_error_to_503(monkeypatch):
    backend_payload = {
        "place": {"display_name": "Messina, Sicily, Italy"},
        "time": {"local": "2026-06-17T12:00"},
        "astro": {
            "zenith_constellation": "Aquila",
            "sun": {"constellation": "Gemini"},
        },
    }

    def fake_generate_daily_reading(payload, model, ollama_url):
        return {
            "kind": "daily_reading",
            "model": model,
            "disclaimer": "Entertainment text generated from astronomical context; not a scientific prediction.",
            "text": "",
            "error": "Ollama error: model not found",
        }

    monkeypatch.setattr(astrogeo_http, "generate_daily_reading", fake_generate_daily_reading)

    status, payload = astrogeo_http.build_daily_reading_payload(
        "aries", "Messina", "2026-06-17", backend_payload
    )

    assert status == 503
    assert payload["ok"] is False
    assert payload["error"]["code"] == "DAILY_READING_UNAVAILABLE"
    assert payload["error"]["message"] == "Ollama error: model not found"


def test_daily_reading_get_without_city_skips_backend_and_uses_sun_only_context(monkeypatch):
    captured = {}

    def fail_run_backend(*args, **kwargs):
        raise AssertionError("run_backend should not be called")

    def fake_sun_constellation(utc_iso):
        captured["utc_iso"] = utc_iso
        return "Gemini"

    def fake_generate_daily_reading(payload, model, ollama_url):
        captured["reading_payload"] = payload
        return {"kind": "daily_reading", "model": model, "text": "A generic line."}

    monkeypatch.setattr(astrogeo_http, "run_backend", fail_run_backend)
    monkeypatch.setattr(astrogeo_http, "sun_constellation", fake_sun_constellation)
    monkeypatch.setattr(astrogeo_http, "generate_daily_reading", fake_generate_daily_reading)

    status, headers, payload = _get(
        "/daily-reading?sign=aries&date=2026-06-17&time=12:00&language=es"
    )

    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert captured["utc_iso"] == "2026-06-17T12:00:00"
    assert captured["reading_payload"] == {
        "sign": "aries",
        "local_date": "2026-06-17",
        "city": "",
        "has_city": False,
        "language": "es",
        "sun_constellation": "Gemini",
        "zenith_constellation": None,
    }
    assert payload["place"] is None
    assert payload["astro"] == {
        "sun_constellation": "Gemini",
        "zenith_constellation": None,
    }
    assert payload["daily_reading"]["text"] == "A generic line."


def test_daily_reading_post_with_empty_city_and_blank_language_defaults_to_english(monkeypatch):
    captured = {}

    def fail_run_backend(*args, **kwargs):
        raise AssertionError("run_backend should not be called")

    def fake_sun_constellation(utc_iso):
        return "Gemini"

    def fake_generate_daily_reading(payload, model, ollama_url):
        captured["reading_payload"] = payload
        return {"kind": "daily_reading", "model": model, "text": "A generic line."}

    monkeypatch.setattr(astrogeo_http, "run_backend", fail_run_backend)
    monkeypatch.setattr(astrogeo_http, "sun_constellation", fake_sun_constellation)
    monkeypatch.setattr(astrogeo_http, "generate_daily_reading", fake_generate_daily_reading)

    status, headers, payload = _post(
        "/astrogeo/v1/daily-reading",
        {"sign": "aries", "city": "   ", "date": "2026-06-17", "time": "12:00", "language": "   "},
    )

    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert captured["reading_payload"]["has_city"] is False
    assert captured["reading_payload"]["language"] == "en"
    assert payload["place"] is None


def test_daily_reading_invalid_language_falls_back_to_english(monkeypatch):
    captured = {}

    def fake_sun_constellation(utc_iso):
        return "Gemini"

    def fake_generate_daily_reading(payload, model, ollama_url):
        captured["reading_payload"] = payload
        return {"kind": "daily_reading", "model": model, "text": "A generic line."}

    monkeypatch.setattr(astrogeo_http, "sun_constellation", fake_sun_constellation)
    monkeypatch.setattr(astrogeo_http, "generate_daily_reading", fake_generate_daily_reading)

    status, _headers, _payload = _get(
        "/daily-reading?sign=aries&date=2026-06-17&time=12:00&language=fr"
    )

    assert status == 200
    assert captured["reading_payload"]["language"] == "en"
