"""
Experimental entertainment reading layer.

This package is intentionally separate from the deterministic GEO -> TIME ->
ASTRO pipeline. It generates poetic text from structured astronomical context
and does not provide astronomy, astrology, or scientific prediction.
"""

from .daily_reading import generate_daily_reading

__all__ = ["generate_daily_reading"]
