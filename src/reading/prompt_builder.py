from __future__ import annotations


def _clean(value: object, fallback: str = "unknown") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def build_daily_reading_prompt(payload: dict) -> str:
    """Build a concise entertainment prompt from structured astro-geo data."""
    sign = _clean(payload.get("sign"))
    local_date = _clean(payload.get("local_date"))
    city = _clean(payload.get("city"))
    sun_constellation = _clean(payload.get("sun_constellation"))
    zenith_constellation = _clean(payload.get("zenith_constellation"))

    return (
        "Write a short playful daily horoscope-style text for entertainment only.\n"
        "Do not present the text as scientific astronomy, astrology, or predictive power.\n"
        "Use the astronomical context only as poetic inspiration.\n"
        "Avoid concrete predictions about money, health, love, or irreversible decisions.\n"
        "Return concise text only, without headings or bullet points.\n\n"
        "Context:\n"
        f"- Sign: {sign}\n"
        f"- Local date: {local_date}\n"
        f"- City: {city}\n"
        f"- Sun constellation: {sun_constellation}\n"
        f"- Zenith constellation: {zenith_constellation}\n"
    )
