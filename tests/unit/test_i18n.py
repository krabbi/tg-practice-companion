"""Tests for bot/i18n.py — t() lookup and fallback behaviour."""

from bot.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, language_name, t


def test_ru_lookup_returns_russian_string() -> None:
    """t() returns the Russian string for a valid key and lang='ru'."""
    result = t("access_denied", "ru")
    assert result == "Доступ запрещён."


def test_en_lookup_returns_english_string() -> None:
    """t() returns the English string for a valid key and lang='en'."""
    result = t("access_denied", "en")
    assert result == "Access denied."


def test_unknown_lang_falls_back_to_default() -> None:
    """t() falls back to DEFAULT_LANGUAGE ('ru') for an unsupported lang code."""
    result = t("access_denied", "de")
    assert result == t("access_denied", DEFAULT_LANGUAGE)


def test_missing_key_returns_raw_key() -> None:
    """t() returns the raw key string when neither catalogue has the key."""
    raw = t("nonexistent_key_xyz", "ru")
    assert raw == "nonexistent_key_xyz"


def test_missing_key_en_fallback_also_returns_raw() -> None:
    """t() returns the raw key for an unknown key in any language."""
    raw = t("nonexistent_key_xyz", "en")
    assert raw == "nonexistent_key_xyz"


def test_default_language_is_ru() -> None:
    """DEFAULT_LANGUAGE constant is 'ru'."""
    assert DEFAULT_LANGUAGE == "ru"


def test_supported_languages_contains_ru_and_en() -> None:
    """SUPPORTED_LANGUAGES contains both 'ru' and 'en'."""
    assert "ru" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES


def test_t_default_lang_param() -> None:
    """t() with no lang argument uses DEFAULT_LANGUAGE."""
    assert t("access_denied") == t("access_denied", DEFAULT_LANGUAGE)


def test_all_en_keys_exist_in_ru() -> None:
    """Every key in the English catalogue also exists in Russian (no orphan keys)."""
    from bot.i18n import _EN, _RU

    for key in _EN:
        assert key in _RU, f"Key '{key}' in _EN but missing from _RU"


def test_language_name_ru() -> None:
    """language_name('ru') returns 'Русский'."""
    assert language_name("ru") == "Русский"


def test_language_name_en() -> None:
    """language_name('en') returns 'English'."""
    assert language_name("en") == "English"


def test_language_name_unknown_returns_code() -> None:
    """language_name returns the raw code for unknown languages."""
    assert language_name("xx") == "xx"
