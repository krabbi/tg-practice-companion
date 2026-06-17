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
        "/skip_day — пропустить практики на сегодня\n"
        "/timezone — изменить часовой пояс\n"
        "/report — отчёт за период"
    ),
    "access_denied": "Доступ запрещён.",
    "voice_not_configured": "Распознавание голоса недоступно (ключ Groq не настроен).",
    "capture_failed": "Не удалось сохранить ответ. Попробуй ещё раз.",
    "want_added": "Добавлено в список желаний! ✨",
    "want_add_failed": "Не удалось добавить. Попробуй ещё раз.",
    "want_no_text": "Напиши, что именно ты хочешь. Например: /want купить гитару",
    "wants_empty": "Список желаний пока пуст. Добавь первый пункт: /want &lt;текст&gt;",
    "wants_list_header": "Твои желания:",
    "want_list_error": "Не удалось загрузить список. Попробуй ещё раз.",
    "want_daily_pick": "💫 Из твоего списка желаний:\n{text}",
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
    # daily AI analysis (AC-11, AC-13)
    "analysis_fallback": (
        "Доброе утро! Ты молодец — каждый день ты делаешь шаги вперёд. "
        "Продолжай практиковать — у тебя всё получится!"
    ),
    # good deeds (AC-10)
    "good_deed_saved": "Записала! Каждое доброе дело делает мир чуточку лучше. 🌟",
    "good_deed_save_failed": "Не удалось сохранить. Попробуй ещё раз.",
    # timezone picker (AC-18, M5)
    "tz_pick_continent": "Выбери континент:",
    "tz_pick_city": "Выбери город / часовой пояс:",
    "tz_set_ok": "Часовой пояс установлен: {tz}. Расписание обновится с ближайшей минуты.",
    "tz_set_error": "Не удалось сохранить часовой пояс. Попробуй ещё раз.",
    "tz_invalid": "Неверный часовой пояс. Начнём сначала — выбери континент:",
    # period report (AC-12, M5)
    "report_pick_period": "Выбери период отчёта:",
    "report_btn_7d": "7 дней",
    "report_btn_30d": "30 дней",
    "report_btn_custom": "Свой период",
    "report_custom_prompt": (
        "Введи период в формате ГГГГ-ММ-ДД ГГГГ-ММ-ДД\n(начало и конец через пробел):"
    ),
    "report_custom_bad_format": (
        "Неверный формат. Введи: ГГГГ-ММ-ДД ГГГГ-ММ-ДД\n(начало и конец через пробел):"
    ),
    "report_error": "Не удалось сформировать отчёт. Попробуй ещё раз.",
    "report_header": "Отчёт за {start} — {end}",
    "report_total_entries": "Записей в дневнике: {n}",
    "report_leads_fraction": "Ведут к целям: {leads} из {total}",
    "report_no_data": "За этот период записей нет.",
    "report_good_deeds_header": "Добрые дела:",
    "report_good_deeds_empty": "Добрых дел за период не записано.",
    "report_practices_header": "Практики отправлены: {n}",
    # /admin command (AC-19)
    "admin_open_button": "Открыть панель администратора",
    "admin_not_configured": "Веб-панель администратора не настроена (WEB_APP_URL не задан).",
}

# English strings — complete canonical set; used when lang == "en" or as fallback.
_EN: dict[str, str] = {
    "start_welcome": (
        "Hello! I'm your personal practice companion. "
        "Every day I'll send you exercises and support. 🌟"
    ),
    "help_text": (
        "Available commands:\n/start — start\n/help — show help\n"
        "/skip_day — skip today's practices\n"
        "/timezone — change timezone\n"
        "/report — period report"
    ),
    "access_denied": "Access denied.",
    "voice_not_configured": "Voice recognition is unavailable (Groq API key not set).",
    "capture_failed": "Could not save your reply. Please try again.",
    "want_added": "Added to your want list! ✨",
    "want_add_failed": "Could not add item. Please try again.",
    "want_no_text": "Tell me what you want. For example: /want buy a guitar",
    "wants_empty": "Your want list is empty. Add the first item: /want &lt;text&gt;",
    "wants_list_header": "Your wants:",
    "want_list_error": "Could not load the list. Please try again.",
    "want_daily_pick": "💫 From your want list:\n{text}",
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
    # daily AI analysis (AC-11, AC-13)
    "analysis_fallback": (
        "Good morning! You're doing great — every day you take steps forward. "
        "Keep practising — you can do it!"
    ),
    # good deeds (AC-10)
    "good_deed_saved": "Saved! Every good deed makes the world a little better. 🌟",
    "good_deed_save_failed": "Could not save. Please try again.",
    # timezone picker (AC-18, M5)
    "tz_pick_continent": "Choose a continent:",
    "tz_pick_city": "Choose a city / timezone:",
    "tz_set_ok": "Timezone set: {tz}. Schedule updates from the next minute.",
    "tz_set_error": "Could not save timezone. Please try again.",
    "tz_invalid": "Invalid timezone. Let's start over — choose a continent:",
    # period report (AC-12, M5)
    "report_pick_period": "Choose report period:",
    "report_btn_7d": "7 days",
    "report_btn_30d": "30 days",
    "report_btn_custom": "Custom period",
    "report_custom_prompt": (
        "Enter the period as YYYY-MM-DD YYYY-MM-DD\n(start and end separated by a space):"
    ),
    "report_custom_bad_format": (
        "Invalid format. Enter: YYYY-MM-DD YYYY-MM-DD\n(start and end separated by a space):"
    ),
    "report_error": "Could not generate report. Please try again.",
    "report_header": "Report for {start} — {end}",
    "report_total_entries": "Journal entries: {n}",
    "report_leads_fraction": "Leading to goals: {leads} of {total}",
    "report_no_data": "No entries found for this period.",
    "report_good_deeds_header": "Good deeds:",
    "report_good_deeds_empty": "No good deeds recorded for this period.",
    "report_practices_header": "Practices sent: {n}",
    # /admin command (AC-19)
    "admin_open_button": "Open admin panel",
    "admin_not_configured": "The admin web panel is not configured (WEB_APP_URL is not set).",
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
