"""Minimal i18n layer — t(key, lang) looks up a localised string."""

DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = {"ru", "en"}

# Russian strings are primary; every key must also exist in _EN as canonical fallback.
_RU: dict[str, str] = {
    "start_welcome": (
        "Привет! Я твой персональный помощник по практикам. "
        "Каждый день буду присылать тебе упражнения и поддержку. 🌟"
    ),
    "help_text": (
        "Доступные команды:\n/start — начать работу\n/help — показать справку\n"
        "/skip_day — пропустить практики на сегодня"
    ),
    "access_denied": "Доступ запрещён.",
    "voice_not_configured": "Распознавание голоса недоступно (ключ Groq не настроен).",
    "capture_failed": "Не удалось сохранить ответ. Попробуй ещё раз.",
    "want_added": "Добавлено в список желаний! ✨",
    "want_add_failed": "Не удалось добавить. Попробуй ещё раз.",
    # skip_day (AC-5)
    "skip_day_confirmed": "Хорошо, практики на сегодня ({date}) пропущены. Завтра продолжим!",
    "skip_day_button": "Пропустить сегодня",
    # delivery errors
    "delivery_error": "Не удалось отправить практику. Пожалуйста, сообщи об этом.",
    # skip_day errors
    "skip_day_error": "Не удалось пропустить день. Попробуй ещё раз.",
    # assessment buttons (AC-8)
    "assess_yes": "Да ✅",
    "assess_no": "Нет ❌",
    # clarify question — deterministic, no LLM (AC-8)
    "assess_clarify": "Ведёт ли тебя это к твоим целям?",
    # assessment errors
    "assessment_failed": "Не удалось сохранить оценку. Попробуй ещё раз.",
    "assessment_already_set": "Оценка уже записана.",
}

# English strings — complete canonical set; used when lang == "en" or as fallback.
_EN: dict[str, str] = {
    "start_welcome": (
        "Hello! I'm your personal practice companion. "
        "Every day I'll send you exercises and support. 🌟"
    ),
    "help_text": (
        "Available commands:\n/start — start\n/help — show help\n/skip_day — skip today's practices"
    ),
    "access_denied": "Access denied.",
    "voice_not_configured": "Voice recognition is unavailable (Groq API key not set).",
    "capture_failed": "Could not save your reply. Please try again.",
    "want_added": "Added to your want list! ✨",
    "want_add_failed": "Could not add item. Please try again.",
    # skip_day (AC-5)
    "skip_day_confirmed": "Done, practices for today ({date}) are skipped. See you tomorrow!",
    "skip_day_button": "Skip today",
    # delivery errors
    "delivery_error": "Could not send the practice. Please let us know.",
    # skip_day errors
    "skip_day_error": "Could not skip the day. Please try again.",
    # assessment buttons (AC-8)
    "assess_yes": "Yes ✅",
    "assess_no": "No ❌",
    # clarify question — deterministic, no LLM (AC-8)
    "assess_clarify": "Does this thought lead you towards your goals?",
    # assessment errors
    "assessment_failed": "Could not save your assessment. Please try again.",
    "assessment_already_set": "Assessment already recorded.",
}

_STRINGS: dict[str, dict[str, str]] = {"ru": _RU, "en": _EN}


def t(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Return the localised string for *key* in *lang*.

    Falls back to English, then returns the raw key if neither catalogue has it.
    """
    effective = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    result = _STRINGS.get(effective, {}).get(key)
    if result is not None:
        return result
    # Fallback to English
    result = _EN.get(key)
    if result is not None:
        return result
    # Last resort: return the key itself so the UI never crashes
    return key


def language_name(lang: str) -> str:
    """Return a human-readable name for a language code."""
    names: dict[str, str] = {"ru": "Русский", "en": "English"}
    return names.get(lang, lang)
