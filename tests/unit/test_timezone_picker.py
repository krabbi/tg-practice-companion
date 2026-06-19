"""Regression tests for curated timezone lists in bot/handlers/timezone_setup.py.

These tests guard against deprecated IANA aliases slipping into the curated lists
and ensure every entry resolves correctly on any tzdata version.
"""

from zoneinfo import ZoneInfo, available_timezones

import pytest

from bot.handlers.timezone_setup import _AMERICA_CURATED

# Build a list of ALL curated lists so the parametrised tests cover every continent.
# When a new _*_CURATED constant is added, import and register it here.
_ALL_CURATED: list[tuple[str, list[str]]] = [
    ("America", _AMERICA_CURATED),
]


# ---------------------------------------------------------------------------
# Correctness of individual entries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("continent,curated", _ALL_CURATED)
def test_all_curated_entries_in_available_timezones(continent: str, curated: list[str]) -> None:
    """Every entry in a curated list must appear in available_timezones()."""
    available = available_timezones()
    missing = [tz for tz in curated if tz not in available]
    assert not missing, (
        f"Curated {continent} entries not in available_timezones(): {missing}. "
        "These are likely deprecated IANA backward-compat aliases."
    )


@pytest.mark.parametrize("continent,curated", _ALL_CURATED)
def test_all_curated_entries_accepted_by_zoneinfo(continent: str, curated: list[str]) -> None:
    """ZoneInfo(tz) must not raise for any curated entry."""
    bad: list[str] = []
    for tz in curated:
        try:
            ZoneInfo(tz)
        except Exception as exc:
            bad.append(f"{tz!r}: {exc}")
    assert not bad, f"ZoneInfo() rejected curated {continent} entries: {bad}"


# ---------------------------------------------------------------------------
# Americas-specific assertions (issue #114)
# ---------------------------------------------------------------------------


def test_america_curated_contains_argentina_canonical() -> None:
    """Canonical Argentina zone must be in curated list; deprecated alias must not."""
    assert "America/Argentina/Buenos_Aires" in _AMERICA_CURATED
    assert "America/Buenos_Aires" not in _AMERICA_CURATED, (
        "America/Buenos_Aires is a deprecated alias — use America/Argentina/Buenos_Aires"
    )


def test_america_curated_contains_montevideo() -> None:
    """Uruguay (Montevideo) must be in the curated Americas list."""
    assert "America/Montevideo" in _AMERICA_CURATED
