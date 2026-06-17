from __future__ import annotations

from .ollama_client import DEFAULT_MODEL, OllamaError, generate_text
from .prompt_builder import build_daily_reading_prompt

DISCLAIMER = "Entertainment text generated from astronomical context; not a scientific prediction."


def generate_daily_reading(
    payload: dict,
    model: str = DEFAULT_MODEL,
    ollama_url: str | None = None,
) -> dict:
    prompt = build_daily_reading_prompt(payload)
    result = {
        "kind": "daily_reading",
        "model": model,
        "disclaimer": DISCLAIMER,
    }

    try:
        kwargs = {"model": model}
        if ollama_url is not None:
            kwargs["url"] = ollama_url
        result["text"] = generate_text(prompt, **kwargs)
    except OllamaError as e:
        result["error"] = str(e)
        result["text"] = ""

    return result
