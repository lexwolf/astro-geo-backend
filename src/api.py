from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs

from astrogeo_pipeline import AstroGeoError, build_astrogeo_payload

ASTROGEO_ROUTE = "/astrogeo/v1/astrogeo"


def json_response(payload: dict[str, Any], status_code: int = 200) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return {
        "status": status_code,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
        "body": body,
    }


def error_response(code: str, message: str, status_code: int) -> dict[str, Any]:
    return json_response(
        {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
        status_code,
    )


def handle_astrogeo_request(query_string: bytes) -> dict[str, Any]:
    params = parse_qs(query_string.decode("utf-8"), keep_blank_values=True)

    def first(name: str) -> str:
        values = params.get(name)
        return values[0] if values else ""

    try:
        payload = build_astrogeo_payload(
            first("city"),
            first("date"),
            first("time"),
        )
    except AstroGeoError as e:
        return error_response(e.code, e.message, e.status_code)
    except Exception:
        return error_response("INTERNAL_ERROR", "Unexpected server error.", 500)

    return json_response(payload)


async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    if scope["type"] != "http":
        raise RuntimeError("Unsupported ASGI scope type.")

    if scope.get("path") != ASTROGEO_ROUTE:
        response = error_response("NOT_FOUND", "Route not found.", 404)
    elif scope.get("method") != "GET":
        response = error_response("METHOD_NOT_ALLOWED", "Method not allowed.", 405)
    else:
        response = handle_astrogeo_request(scope.get("query_string", b""))

    await send(
        {
            "type": "http.response.start",
            "status": response["status"],
            "headers": response["headers"],
        }
    )
    await send({"type": "http.response.body", "body": response["body"]})
