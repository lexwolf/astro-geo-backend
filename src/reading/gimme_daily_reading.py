#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reading.daily_reading import generate_daily_reading  # noqa: E402
from reading.ollama_client import DEFAULT_MODEL  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Experimental entertainment daily reading smoke test; outputs one JSON object."
    )
    p.add_argument("--sign", required=True)
    p.add_argument("--city", required=True)
    p.add_argument("--date", required=True, dest="local_date", help="Local date YYYY-MM-DD")
    p.add_argument("--sun-constellation", required=True)
    p.add_argument("--zenith-constellation", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = {
        "sign": args.sign,
        "local_date": args.local_date,
        "city": args.city,
        "sun_constellation": args.sun_constellation,
        "zenith_constellation": args.zenith_constellation,
    }
    result = generate_daily_reading(payload, model=args.model)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
