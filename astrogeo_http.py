#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date as date_type, time as time_type
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from reading.daily_reading import generate_daily_reading  # noqa: E402
from reading.ollama_client import DEFAULT_MODEL  # noqa: E402

ASTROGEO_PATHS = {"/v1/astrogeo", "/astrogeo/v1/astrogeo"}
DAILY_READING_PATHS = {
    "/daily-reading",
    "/v1/daily-reading",
    "/astrogeo/daily-reading",
    "/astrogeo/v1/daily-reading",
}
DAILY_READING_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EU_DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
DATE_EXPECTATION = "Expected YYYY-MM-DD with year 0001-9999."
EU_DATE_EXPECTATION = "Expected DD-MM-YYYY with year 0001-9999."
ZODIAC_SIGNS = {
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    # CORS: harmless for Unreal, useful for browser tests
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


def error_payload(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


def validate_city(city: str | None) -> str:
    if not isinstance(city, str) or not city.strip():
        raise ValueError("City must be a non-empty string.")
    return " ".join(city.strip().split())


def validate_date(date_s: str | None) -> str:
    value = date_s.strip() if isinstance(date_s, str) else ""
    if not DATE_RE.fullmatch(value):
        raise ValueError(f"Invalid date '{value}'. {DATE_EXPECTATION}")
    try:
        year = int(value[:4])
        month = int(value[5:7])
        day = int(value[8:10])
        if year == 0:
            raise ValueError("year 0 is out of range")
        date_type(year, month, day)
    except ValueError as e:
        raise ValueError(f"Invalid date '{value}'. {DATE_EXPECTATION}") from e
    return value


def validate_eu_date(eu_date_s: str | None) -> str:
    value = eu_date_s.strip() if isinstance(eu_date_s, str) else ""
    if not EU_DATE_RE.fullmatch(value):
        raise ValueError(f"Invalid eu_date '{value}'. {EU_DATE_EXPECTATION}")
    try:
        day = int(value[:2])
        month = int(value[3:5])
        year = int(value[6:10])
        if year == 0:
            raise ValueError("year 0 is out of range")
        date_type(year, month, day)
    except ValueError as e:
        raise ValueError(f"Invalid eu_date '{value}'. {EU_DATE_EXPECTATION}") from e
    return f"{year:04d}-{month:02d}-{day:02d}"


def validate_date_input(date: str | None, eu_date: str | None) -> str:
    date_value = date.strip() if isinstance(date, str) else ""
    eu_date_value = eu_date.strip() if isinstance(eu_date, str) else ""

    if date_value and eu_date_value:
        raise ValueError("Provide either date=YYYY-MM-DD or eu_date=DD-MM-YYYY, not both.")
    if not date_value and not eu_date_value:
        raise ValueError("Missing date. Provide either date=YYYY-MM-DD or eu_date=DD-MM-YYYY.")
    if eu_date_value:
        return validate_eu_date(eu_date_value)
    return validate_date(date_value)


def validate_time(time_s: str | None) -> str:
    value = time_s.strip() if isinstance(time_s, str) else ""
    if not TIME_RE.fullmatch(value):
        raise ValueError(f"Invalid time '{value}'. Expected HH:MM or HH:MM:SS.")
    try:
        time_type.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"Invalid time '{value}'. Expected HH:MM or HH:MM:SS.") from e
    return value


def validate_sign(sign: str | None) -> str:
    value = sign.strip().lower() if isinstance(sign, str) else ""
    if value not in ZODIAC_SIGNS:
        signs = ", ".join(sorted(ZODIAC_SIGNS))
        raise ValueError(f"Invalid sign '{value}'. Expected one of: {signs}.")
    return value


def validate_request(
    city: str | None, date: str | None, time: str | None, eu_date: str | None = None
) -> tuple[int | None, dict | None, str, str, str]:
    try:
        city_v = validate_city(city)
    except ValueError as e:
        return 400, error_payload("INVALID_CITY", str(e)), "", "", ""

    try:
        date_v = validate_date_input(date, eu_date)
    except ValueError as e:
        return 400, error_payload("INVALID_DATE", str(e)), "", "", ""

    try:
        time_v = validate_time(time)
    except ValueError as e:
        return 400, error_payload("INVALID_TIME", str(e)), "", "", ""

    return None, None, city_v, date_v, time_v


def validate_daily_reading_request(
    sign: str | None,
    city: str | None,
    date: str | None,
    time: str | None,
    eu_date: str | None = None,
) -> tuple[int | None, dict | None, str, str, str, str]:
    try:
        sign_v = validate_sign(sign)
    except ValueError as e:
        return 400, error_payload("INVALID_SIGN", str(e)), "", "", "", ""

    status, payload, city_v, date_v, time_v = validate_request(city, date, time, eu_date=eu_date)
    if status is not None:
        return status, payload, "", "", "", ""

    return None, None, sign_v, city_v, date_v, time_v


def geocoding_message(city: str, stderr: str) -> str:
    suffix = "Try adding country/region."
    if suffix in stderr:
        return f"Could not resolve city '{city}'. {suffix}"
    return f"Could not resolve city '{city}'."


def classify_backend_error(exit_code: int, stderr: str, city: str) -> tuple[int, dict]:
    if exit_code == 2:
        return 404, error_payload("GEOCODING_FAILED", geocoding_message(city, stderr))
    if exit_code == 3:
        return 500, error_payload("TIMEZONE_FAILED", "Timezone could not be resolved from coordinates.")
    if exit_code == 4:
        return 500, error_payload("ASTRO_FAILED", "Astronomical context computation failed.")
    return 500, error_payload("ASTRO_FAILED", "Astronomical context computation failed.")


def run_backend(
    venv_python: str,
    main_py: str,
    city: str,
    date: str,
    time: str,
    short_constellation: bool = False,
    timeout_s: float = 25.0,
) -> tuple[int, dict]:
    cmd = [venv_python, main_py, "--city", city, "--date", date, "--time", time]
    if short_constellation:
        cmd.append("--short-constellation")

    env = os.environ.copy()
    env["HOME"] = "/var/lib/astrogeo"  # pins astropy cache to /var/lib/astrogeo/.astropy/cache
    # Important: relative caches (e.g. ./data/...) should land under /var/lib/astrogeo
    cwd = "/var/lib/astrogeo"

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return 504, error_payload("TIMEOUT", f"Backend timed out after {timeout_s:.1f}s")
    except Exception as e:
        print(f"Failed to launch backend process: {e!r}", file=sys.stderr)
        return 500, error_payload("INTERNAL_ERROR", "Unexpected server error.")

    if proc.returncode != 0:
        # Keep stderr for logs/debugging, but avoid dumping megabytes.
        stderr = (proc.stderr or "").strip()
        if len(stderr) > 4000:
            stderr = stderr[:4000] + " …(truncated)"
        print(f"Backend exited {proc.returncode}: {stderr}", file=sys.stderr)
        return classify_backend_error(proc.returncode, stderr, city)

    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        snippet = raw[:1000] + (" …(truncated)" if len(raw) > 1000 else "")
        print(f"Backend did not return valid JSON: {snippet}", file=sys.stderr)
        return 500, error_payload("ASTRO_FAILED", "Astronomical context computation failed.")

    return 200, data


def build_daily_reading_payload(sign: str, city: str, date: str, backend_payload: dict) -> tuple[int, dict]:
    try:
        place = backend_payload["place"]
        time_payload = backend_payload["time"]
        astro_payload = backend_payload["astro"]
        sun_constellation = astro_payload["sun"]["constellation"]
        zenith_constellation = astro_payload["zenith_constellation"]
    except (KeyError, TypeError):
        return 500, error_payload("ASTRO_FAILED", "Astronomical context computation failed.")

    display_city = place.get("display_name", city) if isinstance(place, dict) else city
    local_date = date
    if isinstance(time_payload, dict) and isinstance(time_payload.get("local"), str):
        local_date = time_payload["local"].split("T", 1)[0]

    reading_input = {
        "sign": sign,
        "local_date": local_date,
        "city": display_city,
        "sun_constellation": sun_constellation,
        "zenith_constellation": zenith_constellation,
    }
    daily_reading = generate_daily_reading(
        reading_input,
        model=DEFAULT_MODEL,
        ollama_url=DAILY_READING_OLLAMA_URL,
    )
    if daily_reading.get("error"):
        return 503, error_payload("DAILY_READING_UNAVAILABLE", daily_reading["error"])

    return 200, {
        "place": place,
        "time": time_payload,
        "astro": {
            "sun_constellation": sun_constellation,
            "zenith_constellation": zenith_constellation,
        },
        "daily_reading": daily_reading,
    }


def build_daily_reading_response(
    server,
    sign: str | None,
    city: str | None,
    date: str | None,
    time: str | None,
    eu_date: str | None = None,
) -> tuple[int, dict]:
    status, payload, sign, city, date, time = validate_daily_reading_request(
        sign, city, date, time, eu_date=eu_date
    )
    if status is not None:
        return status, payload

    status, backend_payload = run_backend(server.venv_python, server.main_py, city, date, time)
    if status != 200:
        return status, backend_payload

    return build_daily_reading_payload(sign, city, date, backend_payload)


class Handler(BaseHTTPRequestHandler):
    server_version = "astrogeo-http/0.1"

    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            return json_response(self, 200, {"ok": True})

        if parsed.path in DAILY_READING_PATHS:
            qs = parse_qs(parsed.query)
            sign = qs.get("sign", [None])[0]
            city = qs.get("city", [None])[0]
            date = qs.get("date", [None])[0]
            eu_date = qs.get("eu_date", [None])[0]
            time = qs.get("time", [None])[0]

            status, payload = build_daily_reading_response(
                self.server, sign, city, date, time, eu_date=eu_date
            )
            return json_response(self, status, payload)

        if parsed.path not in ASTROGEO_PATHS:
            return json_response(self, 404, error_payload("NOT_FOUND", "Unknown endpoint"))

        qs = parse_qs(parsed.query)
        city = qs.get("city", [None])[0]
        date = qs.get("date", [None])[0]
        eu_date = qs.get("eu_date", [None])[0]
        time = qs.get("time", [None])[0]
        short = (qs.get("short_constellation", ["false"])[0] or "false").lower() in ("1", "true", "yes")

        status, payload, city, date, time = validate_request(city, date, time, eu_date=eu_date)
        if status is not None:
            return json_response(self, status, payload)

        status, payload = run_backend(
            self.server.venv_python, self.server.main_py, city, date, time, short_constellation=short
        )
        return json_response(self, status, payload)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        body = self.rfile.read(length) if length > 0 else b""
        try:
            req = json.loads(body.decode("utf-8") if body else "{}")
        except Exception:
            return json_response(self, 400, error_payload("BAD_INPUT", "POST body must be JSON"))

        if not isinstance(req, dict):
            return json_response(self, 400, error_payload("BAD_INPUT", "POST body must be a JSON object"))

        parsed = urlparse(self.path)
        if parsed.path in DAILY_READING_PATHS:
            status, payload = build_daily_reading_response(
                self.server,
                req.get("sign"),
                req.get("city"),
                req.get("date"),
                req.get("time"),
                eu_date=req.get("eu_date"),
            )
            return json_response(self, status, payload)

        if parsed.path not in ASTROGEO_PATHS:
            return json_response(self, 404, error_payload("NOT_FOUND", "Unknown endpoint"))

        city = req.get("city")
        date = req.get("date")
        eu_date = req.get("eu_date")
        time = req.get("time")
        short = bool(req.get("short_constellation", False))

        status, payload, city, date, time = validate_request(city, date, time, eu_date=eu_date)
        if status is not None:
            return json_response(self, status, payload)

        status, payload = run_backend(
            self.server.venv_python, self.server.main_py, city, date, time, short_constellation=short
        )
        return json_response(self, status, payload)

    def log_message(self, fmt: str, *args):
        # Keep stdout clean; systemd will capture if you later enable it.
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8008)
    ap.add_argument("--venv-python", default="/opt/astrogeo/venv/bin/python")
    ap.add_argument("--main-py", default="/srv/astro-geo-backend/astro-geo-backend/src/main.py")
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.venv_python = args.venv_python
    httpd.main_py = args.main_py

    sys.stderr.write(f"Listening on http://{args.host}:{args.port}\n")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
