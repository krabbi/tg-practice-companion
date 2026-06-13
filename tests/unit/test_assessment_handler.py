"""Unit tests for the assessment handler covering edge cases and missing lines."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message, User

from bot.exceptions import AssessmentError
from bot.services.assessment_service import AssessmentResult, AssessmentService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_callback(data: str, user_id: int = 123) -> MagicMock:
    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.data = data
    user = MagicMock(spec=User)
    user.id = user_id
    callback.from_user = user
    msg = MagicMock(spec=Message)
    msg.edit_reply_markup = AsyncMock()
    msg.answer = AsyncMock()
    callback.message = msg
    return callback


def _make_assessment_service(
    raises: Exception | None = None,
    leads_to_goals: bool = True,
) -> MagicMock:
    svc = MagicMock(spec=AssessmentService)
    if raises:
        svc.record = AsyncMock(side_effect=raises)
    else:
        svc.record = AsyncMock(
            return_value=AssessmentResult(
                assessment_id=uuid.uuid4(),
                leads_to_goals=leads_to_goals,
                set_via="button",
            )
        )
    return svc


# ---------------------------------------------------------------------------
# cb_assess handler via router
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_assess_yes_records_assessment() -> None:
    """assess:<id>:yes records assessment with leads_to_goals=True."""
    from bot.handlers.assessment import create_router

    router = create_router()
    entry_id = uuid.uuid4()
    callback = _make_callback(f"assess:{entry_id}:yes")
    svc = _make_assessment_service(leads_to_goals=True)

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    svc.record.assert_awaited_once()
    _, kwargs = svc.record.call_args
    assert kwargs["leads_to_goals"] is True
    assert kwargs["set_via"] == "button"
    assert kwargs["journal_entry_id"] == entry_id
    callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)


@pytest.mark.asyncio
async def test_cb_assess_no_records_assessment() -> None:
    """assess:<id>:no records assessment with leads_to_goals=False."""
    from bot.handlers.assessment import create_router

    router = create_router()
    entry_id = uuid.uuid4()
    callback = _make_callback(f"assess:{entry_id}:no")
    svc = _make_assessment_service(leads_to_goals=False)

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    _, kwargs = svc.record.call_args
    assert kwargs["leads_to_goals"] is False


@pytest.mark.asyncio
async def test_cb_assess_no_from_user_returns_early() -> None:
    """cb_assess returns early when from_user is None."""
    from bot.handlers.assessment import create_router

    router = create_router()
    entry_id = uuid.uuid4()
    callback = _make_callback(f"assess:{entry_id}:yes")
    callback.from_user = None
    svc = _make_assessment_service()

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    svc.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_cb_assess_no_message_returns_early() -> None:
    """cb_assess returns early when callback.message is None."""
    from bot.handlers.assessment import create_router

    router = create_router()
    entry_id = uuid.uuid4()
    callback = _make_callback(f"assess:{entry_id}:yes")
    callback.message = None
    svc = _make_assessment_service()

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    svc.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_cb_assess_malformed_data_returns_early() -> None:
    """Malformed callback data is ignored gracefully."""
    from bot.handlers.assessment import create_router

    router = create_router()
    callback = _make_callback("assess:not-a-valid-format")
    svc = _make_assessment_service()

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    svc.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_cb_assess_invalid_uuid_returns_early() -> None:
    """Invalid UUID in callback data is handled without crashing."""
    from bot.handlers.assessment import create_router

    router = create_router()
    callback = _make_callback("assess:not-a-uuid:yes")
    svc = _make_assessment_service()

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    svc.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_cb_assess_assessment_error_edits_keyboard_and_informs_user() -> None:
    """AssessmentError (duplicate) removes keyboard and replies with already_set message."""
    from bot.handlers.assessment import create_router

    router = create_router()
    entry_id = uuid.uuid4()
    callback = _make_callback(f"assess:{entry_id}:yes")
    svc = _make_assessment_service(raises=AssessmentError("already has a self-assessment"))

    await router.callback_query.handlers[0].call(callback, assessment_service=svc)

    callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)
    callback.message.answer.assert_awaited_once()
    from bot.i18n import t

    assert t("assessment_already_set", "ru") in callback.message.answer.call_args.args[0]


# ---------------------------------------------------------------------------
# clarify_keyboard helper
# ---------------------------------------------------------------------------


def test_clarify_keyboard_structure() -> None:
    """clarify_keyboard returns an InlineKeyboardMarkup with yes/no buttons."""
    from bot.handlers.assessment import clarify_keyboard
    from bot.i18n import t

    entry_id = str(uuid.uuid4())
    kb = clarify_keyboard(entry_id)

    assert len(kb.inline_keyboard) == 1
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2

    yes_btn, no_btn = buttons
    assert yes_btn.callback_data == f"assess:{entry_id}:yes"
    assert no_btn.callback_data == f"assess:{entry_id}:no"
    assert yes_btn.text == t("assess_yes", "ru")
    assert no_btn.text == t("assess_no", "ru")
