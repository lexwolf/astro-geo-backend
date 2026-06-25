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
├── reading/
│   ├── prompt_builder.py        # Experimental entertainment prompt builder
│   ├── ollama_client.py         # Optional local Ollama text generation
│   ├── daily_reading.py         # Daily reading wrapper
│   ├── gimme_daily_reading.py   # Daily reading smoke-test CLI
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

### Optional experimental daily reading layer

The `src/reading/` package is an optional entertainment / poetic text
generation layer. It is not part of the deterministic GEO → TIME → ASTRO
pipeline, does not change the meaning of the `astro` modules, and must not be
treated as astronomy or scientific prediction.

To try it locally, install Ollama separately and pull the small default model:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama run llama3.2:3b
```

If Ollama is installed but not running, start it with:

```bash
ollama serve
```

Smoke test the experimental layer directly:

```bash
python3 src/reading/gimme_daily_reading.py \
  --sign aries \
  --city Messina \
  --date 2026-06-17 \
  --sun-constellation Gemini \
  --zenith-constellation Aquila
```

When running the HTTP shim locally, the same experimental entertainment layer is
available at `GET /daily-reading`. This endpoint first computes the normal
deterministic astro-geo context, then uses that context only as poetic
inspiration for generated text. It is not astronomy, not a scientific
prediction, and not part of the deterministic `/v1/astrogeo` JSON contract.

```bash
curl "http://127.0.0.1:8008/daily-reading?sign=aries&city=Messina&date=2026-06-17&time=12:00"
curl "http://127.0.0.1:8008/daily-reading?sign=aries&date=2026-06-17&time=12:00"
curl "http://127.0.0.1:8008/daily-reading?sign=aries&city=Messina&date=2026-06-17&time=12:00&language=it"
curl "http://127.0.0.1:8008/daily-reading?sign=aries&city=Messina&date=2026-06-17&time=12:00&language=es"
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

CLI dates are accepted only in four-digit `YYYY-MM-DD` form, with years from
`0001` through `9999`. This includes zero-padded historical years such as
`0100-08-25`, `0050-08-25`, and `0001-08-25`; shorter forms such as
`100-08-25` are invalid.

Historical dates are treated mathematically using Python/Astropy's proleptic
Gregorian calendar and astronomical approximations, not as historically local
civil calendars.

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
    "local_date_display": "23-12-1977",
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

- `warnings` is populated in case of DST ambiguities, non-existent local times
  (spring/fall transitions), or historical dates outside the modern
  high-confidence range.
- The JSON output is intended to be consumed by downstream astronomical
  or physical modules.

---

## HTTP API smoke checks

The deployed endpoint always returns JSON, including validation and lookup
errors. These checks should parse cleanly with `jq`:

The deployed HTTP shim is `astrogeo_http.py` and serves `/v1/astrogeo`
directly, or `/astrogeo/v1/astrogeo` when mounted behind that prefix.

The HTTP API accepts either `date=YYYY-MM-DD` or `eu_date=DD-MM-YYYY`. Provide
only one date parameter per request; European dates are canonicalized internally
to the same date used by the ISO parser.

```bash
curl -sG 'https://lupoegatta.site/astrogeo/v1/astrogeo' \
  --data-urlencode 'city=Cosnzza' \
  --data-urlencode 'date=1982-08-25' \
  --data-urlencode 'time=12:00' | jq .
```

```bash
curl -sG 'https://lupoegatta.site/astrogeo/v1/astrogeo' \
  --data-urlencode 'city=Cosenza' \
  --data-urlencode 'eu_date=25-08-1982' \
  --data-urlencode 'time=12:00' | jq .
```

```bash
curl -sG 'https://lupoegatta.site/astrogeo/v1/astrogeo' \
  --data-urlencode 'city=Cosenza' \
  --data-urlencode 'date=1982-99-25' \
  --data-urlencode 'time=12:00' | jq .
```

Expected error responses follow this shape:

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_DATE",
    "message": "Invalid date '1982-99-25'. Expected YYYY-MM-DD with year 0001-9999."
  }
}
```

---

## Deployment to lupoegatta

The `lupoegatta` deployment is managed by scripts under `deploy/`.
The local deployer uploads a release bundle to `/home/ncadmin/astrogeo-deploy`
and then runs a sudo installer on the server.

```bash
deploy/deploy_lupoegatta.sh
```

The installer deploys releases under `/opt/astrogeo/releases/<timestamp>`,
points `/opt/astrogeo/current` at the active release, installs the package into
`/opt/astrogeo/venv`, updates `astrogeo-http.service`, restarts it, and checks
`http://127.0.0.1:8008/healthz`.

The service explicitly runs the backend CLI from:

```text
/opt/astrogeo/current/src/main.py
```

This removes the previous dependency on the old editable source path under
`/srv/astro-geo-backend/astro-geo-backend`.

Useful options:

```bash
deploy/deploy_lupoegatta.sh --skip-tests
deploy/deploy_lupoegatta.sh --allow-dirty
ASTROGEO_REMOTE=ncadmin@lupoegatta deploy/deploy_lupoegatta.sh
```

Manual rollback on the server:

```bash
sudo ln -sfn /opt/astrogeo/releases/<previous-release> /opt/astrogeo/current
sudo install -o root -g root -m 0755 /opt/astrogeo/current/astrogeo_http.py /opt/astrogeo/astrogeo_http.py
sudo systemctl restart astrogeo-http.service
```

---

## Design notes

- Geocoding uses **Nominatim** with caching and rate limiting.
- Time conversion uses **IANA timezones** and explicit DST policies.
- All components are deterministic and testable.
- Astro computations are powered by **Astropy** and use official IAU
  constellation boundaries.

More advanced astronomical logic (e.g. detailed ephemerides, house systems,
interpretations) belongs in separate modules built on top of this backend.

The optional `reading` layer is one such separate module: it can turn structured
astro-geo context into concise playful prose, but only as entertainment text
generation.
