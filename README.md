# astro-geo-backend

Backend utilities for resolving **geographical location** and **civil time**
information in a deterministic and reproducible way.

This project provides a small, composable backend that performs:

- **Geocoding**: city / place name → coordinates and IANA timezone
- **Civil time resolution**: local date & time → UTC, with explicit DST handling

The output is a single structured JSON object suitable for further
astronomical or physical computations.

⚠️ No astrological, horoscope, or interpretative logic is implemented.

---

## Project structure

```
src/
├── geo/
│   ├── geocode_city.py        # Geocoding + cache + rate limiting
│   ├── gimme_geocode_city.py  # GEO CLI helper
│   ├── gimme_tzname.py        # GEO CLI helper (timezone only)
│   └── __init__.py
│
├── civil_time/
│   ├── civil_time.py          # Local → UTC conversion with DST policies
│   ├── gimme_civil_time.py    # TIME CLI helper
│   └── __init__.py
│
└── main.py                    # GEO → TIME orchestration CLI
```

---

## Installation (development)

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional (recommended) dependency for timezone resolution:

```bash
pip install timezonefinder
```

---

## Usage

Run the main CLI from the repository root:

```bash
python3 src/main.py \
  --city "Cosenza, Calabria, Italy" \
  --date 1985-03-12 \
  --time 08:30
```

### Output

The program prints **one single JSON object** to stdout:

```json
{
  "place": {
    "display_name": "Cosenza, Calabria, Italia",
    "lat": 39.5966853,
    "lon": 16.3330556,
    "tzid": "Europe/Rome"
  },
  "time": {
    "local": "1985-03-12T08:30",
    "utc": "1985-03-12T07:30Z",
    "warnings": []
  }
}
```

- `warnings` is populated only in case of DST ambiguities or non-existent
  local times (spring/fall transitions).
- The JSON output is intended to be consumed by downstream astronomical
  or physical modules.

---

## Design notes

- Geocoding uses **Nominatim** with caching and rate limiting.
- Time conversion uses **IANA timezones** and explicit DST policies.
- All components are deterministic and testable.
- This repository intentionally stops at **GEO → TIME** resolution.

Astronomical logic (e.g. zenith, ephemerides, constellations) belongs in
separate modules built on top of this backend.
