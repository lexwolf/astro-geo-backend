# astro-geo-backend

Backend utilities for resolving **geographical location**, **civil time**, and
basic **astronomical context** in a deterministic and reproducible way.

This project provides a small, composable backend that performs:

- **Geocoding**: city / place name → coordinates and IANA timezone
- **Civil time resolution**: local date & time → UTC, with explicit DST handling
- **Astro context**: zenith constellation + Sun constellation/ecliptic/ICRS at UTC

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
├── astro/
│   ├── zenith_constellation.py  # IAU constellation at zenith
│   ├── sun_on_the_ecliptic.py   # Sun ecliptic + ICRS + constellation
│   ├── gimme_zenith_constellation.py
│   ├── gimme_sun_on_the_ecliptic.py
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

---

## Usage

Run the main CLI from the repository root:

```bash
python3 src/main.py \
  --city "Tumbaco" \
  --date 1977-12-23 \
  --time 01:00
```

### Output

The program prints **one single JSON object** to stdout:

```json
{
  "place": {
    "display_name": "Tumbaco, Quito, Pichincha, Ecuador",
    "lat": -0.2122548,
    "lon": -78.4044951,
    "tzid": "America/Guayaquil"
  },
  "time": {
    "local": "1977-12-23T01:00",
    "utc": "1977-12-23T06:00Z",
    "warnings": []
  },
  "astro": {
    "zenith_constellation": "Monoceros",
    "sun": {
      "constellation": "Sagittarius",
      "ecliptic": {
        "lon_deg": 271.6017251883241,
        "lat_deg": -0.002933940728190138
      },
      "icrs": {
        "ra_deg": 309.5897357908915,
        "dec_deg": -19.438574188148745
      }
    }
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
- Astro computations are powered by **Astropy** and use official IAU
  constellation boundaries.

More advanced astronomical logic (e.g. detailed ephemerides, house systems,
interpretations) belongs in separate modules built on top of this backend.
