#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


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


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


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
        return 504, error_payload(
            "TIMEOUT",
            f"Backend timed out after {timeout_s:.1f}s",
            {"timeout_s": timeout_s},
        )
    except Exception as e:
        return 500, error_payload("INTERNAL", "Failed to launch backend process", {"exc": repr(e)})

    if proc.returncode != 0:
        # Keep stderr for logs/debugging, but avoid dumping megabytes.
        stderr = (proc.stderr or "").strip()
        if len(stderr) > 4000:
            stderr = stderr[:4000] + " …(truncated)"
        return 502, error_payload(
            "BACKEND_ERROR",
            "Backend returned non-zero exit code",
            {"exit_code": proc.returncode, "stderr": stderr},
        )

    raw = (proc.stdout or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        snippet = raw[:1000] + (" …(truncated)" if len(raw) > 1000 else "")
        return 502, error_payload(
            "BAD_BACKEND_JSON",
            "Backend did not return valid JSON",
            {"stdout_snippet": snippet},
        )

    return 200, data


class Handler(BaseHTTPRequestHandler):
    server_version = "astrogeo-http/0.1"

    def do_OPTIONS(self):
        json_response(self, 200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            return json_response(self, 200, {"ok": True})

        if parsed.path != "/v1/astrogeo":
            return json_response(self, 404, error_payload("NOT_FOUND", "Unknown endpoint"))

        qs = parse_qs(parsed.query)
        city = (qs.get("city", [None])[0] or "").strip()
        date = (qs.get("date", [None])[0] or "").strip()
        time = (qs.get("time", [None])[0] or "").strip()
        short = (qs.get("short_constellation", ["false"])[0] or "false").lower() in ("1", "true", "yes")

        if not city or not date or not time:
            return json_response(
                self,
                400,
                error_payload(
                    "BAD_INPUT",
                    "Missing required query parameters: city, date, time",
                    {"got": {"city": bool(city), "date": bool(date), "time": bool(time)}},
                ),
            )

        status, payload = run_backend(
            self.server.venv_python, self.server.main_py, city, date, time, short_constellation=short
        )
        return json_response(self, status, payload)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/v1/astrogeo":
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

        city = str(req.get("city", "")).strip()
        date = str(req.get("date", "")).strip()
        time = str(req.get("time", "")).strip()
        short = bool(req.get("short_constellation", False))

        if not city or not date or not time:
            return json_response(
                self,
                400,
                error_payload(
                    "BAD_INPUT",
                    "Missing required JSON fields: city, date, time",
                    {"got": {"city": bool(city), "date": bool(date), "time": bool(time)}},
                ),
            )

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

