"""i18n key-parity test — AC-14 (M5).

Asserts that set(_EN) == set(_RU): every key must exist in both catalogues.
Both catalogues must be non-empty.
"""

from bot.i18n import _EN, _RU


def test_en_keys_and_ru_keys_are_identical_sets() -> None:
    """Every key in _EN must be present in _RU and vice versa."""
    en_keys = set(_EN.keys())
    ru_keys = set(_RU.keys())

    missing_from_ru = en_keys - ru_keys
    missing_from_en = ru_keys - en_keys

    assert not missing_from_ru, f"Keys in _EN but missing from _RU: {missing_from_ru}"
    assert not missing_from_en, f"Keys in _RU but missing from _EN: {missing_from_en}"


def test_en_catalogue_is_non_empty() -> None:
    """_EN must contain at least one key."""
    assert len(_EN) > 0


def test_ru_catalogue_is_non_empty() -> None:
    """_RU must contain at least one key."""
    assert len(_RU) > 0


def test_all_en_values_are_non_empty_strings() -> None:
    """Every value in _EN must be a non-empty string."""
    for key, value in _EN.items():
        assert isinstance(value, str), f"_EN[{key!r}] is not a string"
        assert value, f"_EN[{key!r}] is an empty string"


def test_all_ru_values_are_non_empty_strings() -> None:
    """Every value in _RU must be a non-empty string."""
    for key, value in _RU.items():
        assert isinstance(value, str), f"_RU[{key!r}] is not a string"
        assert value, f"_RU[{key!r}] is an empty string"
