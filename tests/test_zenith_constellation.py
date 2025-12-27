import pytest

from astro.zenith_constellation import constellation_at_zenith, zenith_debug


@pytest.fixture(autouse=True)
def _no_iers_network(monkeypatch):
    """
    Avoid network during tests: astropy may try to download IERS tables.
    We disable auto-download so tests are deterministic and CI-friendly.
    """
    try:
        from astropy.utils import iers
    except Exception:
        return

    # Disable auto-download and don't fail hard if IERS tables are old/missing.
    iers.conf.auto_download = False
    iers.conf.iers_degraded_accuracy = "warn"


def test_zenith_constellation_name():
    # Reference point (Parma-ish) and timestamp from our verified CLI run.
    name = constellation_at_zenith(
        "2025-12-27T12:00:00Z",
        44.695201,
        10.097987,
        short=False,
    )
    assert str(name) == "Lyra"


def test_zenith_constellation_abbrev():
    abbr = constellation_at_zenith(
        "2025-12-27T12:00:00Z",
        44.695201,
        10.097987,
        short=True,
    )
    assert str(abbr) == "Lyr"


def test_zenith_dec_close_to_latitude():
    r = zenith_debug("2025-12-27T12:00:00Z", 44.695201, 10.097987)

    # In practice, dec should be very close to observer latitude.
    # We allow a small tolerance because we transform via AltAz -> ICRS.
    assert abs(r.dec_deg - 44.695201) < 0.1  # degrees (~6 arcmin)


def test_zenith_ra_in_range():
    r = zenith_debug("2025-12-27T12:00:00Z", 44.695201, 10.097987)
    assert 0.0 <= r.ra_deg < 360.0
