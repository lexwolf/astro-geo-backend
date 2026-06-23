from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:3b"


class OllamaError(RuntimeError):
    """Raised when local Ollama text generation cannot complete."""


def generate_text(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
    timeout_s: float = 180.0,
) -> str:
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        details = e.read().decode("utf-8", errors="replace")
        raise OllamaError(f"Ollama returned HTTP {e.code}: {details}") from e
    except URLError as e:
        raise OllamaError(
            "Could not connect to Ollama at http://localhost:11434. "
            "Run `ollama serve` or start Ollama normally, then try again."
        ) from e
    except TimeoutError as e:
        raise OllamaError("Ollama did not respond before the request timed out.") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise OllamaError("Ollama returned a non-JSON response.") from e

    if data.get("error"):
        raise OllamaError(f"Ollama error: {data['error']}")

    text = data.get("response")
    if not isinstance(text, str):
        raise OllamaError("Ollama response did not contain generated text.")
    return text.strip()
