import pytest
from datetime import date, time, timezone

from civil_time.civil_time import (
    resolve_local_to_utc,
    AmbiguousLocalTime,
    NonExistentLocalTime,
)

TZ = "Europe/Rome"


def test_normal_winter_time():
    # 2025-01-15 12:00 in Rome is CET (UTC+1) -> 11:00Z
    r = resolve_local_to_utc(date(2025, 1, 15), time(12, 0), TZ)
    assert r.utc == r.utc.replace(tzinfo=timezone.utc)  # aware UTC
    assert r.utc.isoformat() == "2025-01-15T11:00:00+00:00"
    assert r.offset_seconds == 3600


def test_normal_summer_time():
    # 2025-07-15 12:00 in Rome is CEST (UTC+2) -> 10:00Z
    r = resolve_local_to_utc(date(2025, 7, 15), time(12, 0), TZ)
    assert r.utc.isoformat() == "2025-07-15T10:00:00+00:00"
    assert r.offset_seconds == 7200


def test_ambiguous_time_raises():
    # DST ends in Italy on 2025-10-26; 02:30 happens twice
    with pytest.raises(AmbiguousLocalTime):
        resolve_local_to_utc(date(2025, 10, 26), time(2, 30), TZ, ambiguous="raise")


def test_ambiguous_time_earliest():
    # earliest = first occurrence = still DST (UTC+2) => 00:30Z
    r = resolve_local_to_utc(date(2025, 10, 26), time(2, 30), TZ, ambiguous="earliest")
    assert r.utc.isoformat() == "2025-10-26T00:30:00+00:00"
    assert r.fold == 0


def test_ambiguous_time_latest():
    # latest = second occurrence = standard time (UTC+1) => 01:30Z
    r = resolve_local_to_utc(date(2025, 10, 26), time(2, 30), TZ, ambiguous="latest")
    assert r.utc.isoformat() == "2025-10-26T01:30:00+00:00"
    assert r.fold == 1


def test_nonexistent_time_raises():
    # DST starts in Italy on 2025-03-30; 02:30 does NOT exist
    with pytest.raises(NonExistentLocalTime):
        resolve_local_to_utc(date(2025, 3, 30), time(2, 30), TZ, nonexistent="raise")


def test_nonexistent_time_shift_forward():
    # shift_forward should land on the first valid civil time after the gap
    r = resolve_local_to_utc(
        date(2025, 3, 30), time(2, 30), TZ, nonexistent="shift_forward"
    )
    # first valid time is 03:00 local, which is UTC+2 => 01:00Z
    assert r.utc.isoformat() == "2025-03-30T01:00:00+00:00"
