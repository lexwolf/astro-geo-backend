#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date as date_type, time as time_type
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ASTROGEO_PATHS = {"/v1/astrogeo", "/astrogeo/v1/astrogeo"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


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
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.")
    try:
        date_type.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from e
    return value


def validate_time(time_s: str | None) -> str:
    value = time_s.strip() if isinstance(time_s, str) else ""
    if not TIME_RE.fullmatch(value):
        raise ValueError(f"Invalid time '{value}'. Expected HH:MM or HH:MM:SS.")
    try:
        time_type.fromisoformat(value)
    except ValueError as e:
        raise ValueError(f"Invalid time '{value}'. Expected HH:MM or HH:MM:SS.") from e
    return value


def validate_request(city: str | None, date: str | None, time: str | None) -> tuple[int | None, dict | None, str, str, str]:
    try:
        city_v = validate_city(city)
    except ValueError as e:
        return 400, error_payload("INVALID_CITY", str(e)), "", "", ""

    try:
        date_v = validate_date(date)
    except ValueError as e:
        return 400, error_payload("INVALID_DATE", str(e)), "", "", ""

    try:
        time_v = validate_time(time)
    except ValueError as e:
        return 400, error_payload("INVALID_TIME", str(e)), "", "", ""

    return None, None, city_v, date_v, time_v


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


class Handler(BaseHTTPRequestHandler):
    server_version = "astrogeo-http/0.1"

    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            return json_response(self, 200, {"ok": True})

        if parsed.path not in ASTROGEO_PATHS:
            return json_response(self, 404, error_payload("NOT_FOUND", "Unknown endpoint"))

        qs = parse_qs(parsed.query)
        city = qs.get("city", [None])[0]
        date = qs.get("date", [None])[0]
        time = qs.get("time", [None])[0]
        short = (qs.get("short_constellation", ["false"])[0] or "false").lower() in ("1", "true", "yes")

        status, payload, city, date, time = validate_request(city, date, time)
        if status is not None:
            return json_response(self, status, payload)

        status, payload = run_backend(
            self.server.venv_python, self.server.main_py, city, date, time, short_constellation=short
        )
        return json_response(self, status, payload)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ASTROGEO_PATHS:
            return json_response(self, 404, error_payload("NOT_FOUND", "Unknown endpoint"))

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        body = self.rfile.read(length) if length > 0 else b""
        try:
            req = json.loads(body.decode("utf-8") if body else "{}")
        except Exception:
            return json_response(self, 400, error_payload("BAD_INPUT", "POST body must be JSON"))

        city = req.get("city")
        date = req.get("date")
        time = req.get("time")
        short = bool(req.get("short_constellation", False))

        status, payload, city, date, time = validate_request(city, date, time)
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
