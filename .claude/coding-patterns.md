# Coding Patterns — tg-practice-companion

Detailed code patterns for the 3-layer architecture. Read this when implementing features.
For the quick summary see `CLAUDE.md`.

---

## Handler pattern

Handlers are thin: validate input, call one service, reply to user. No business logic.

```python
# Good
async def handle_want_add(message: Message, want_list_service: WantListService) -> None:
    """Handle /want <text> — add an item to the want list."""
    try:
        result = await want_list_service.add(message.from_user.id, text)
        await message.answer(t("want_added", lang))
    except WantListError:
        await message.answer(t("want_add_failed", lang))

# Bad — business logic in handler
async def handle_want_add(message: Message, session: AsyncSession) -> None:
    item = WantListItem(user_id=message.from_user.id, text=message.text)
    session.add(item)
    await session.commit()
```

### Callback handler pattern

```python
@router.callback_query(F.data.startswith("assess:"))
async def cb_assess(
    callback: CallbackQuery,
    assessment_service: AssessmentService,
) -> None:
    """One-line docstring."""
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    # ... call service, reply to user ...
```

### Optional services

Services that depend on external credentials (`transcription_service` when `GROQ_API_KEY`
is empty, `ai_analysis_service` / `llm_client` when the cost guardrail blocks calls) are
injected as `None` when not configured. Always guard before use:

```python
async def handle_voice(message: Message, transcription_service: TranscriptionService | None = None) -> None:
    if transcription_service is None:
        await message.answer(t("voice_not_configured", lang))
        return
    ...
```

### i18n — every user-facing string

All UI strings go through `t(key, lang)` from `bot/i18n.py` (AC-14). Never hardcode a
user-visible string in a handler or service. `_RU` is primary, `_EN` is the canonical
complete fallback.

### HTML rendering

When using `parse_mode="HTML"`, always escape LLM-sourced or user-sourced content:

```python
import html

text = f"📊 <b>{html.escape(title)}</b>\n\n{html.escape(analysis_text)}"
await message.answer(text, parse_mode="HTML")
```

---

## Service pattern

Services own all business logic and transaction boundaries. No Telegram API calls.

```python
class JournalService:
    """Captures replies into the journal and binds them to practices."""

    def __init__(self, session: AsyncSession, journal_repo: JournalRepository,
                 prompt_repo: PendingPromptRepository) -> None:
        self._session = session
        self._journal_repo = journal_repo
        self._prompt_repo = prompt_repo

    async def capture(self, user_id: int, text: str, source: EntrySource) -> CaptureResult:
        """Bind the reply to a pending prompt, store the entry, consume the prompt."""
        prompt = await self._prompt_repo.newest_unconsumed(user_id)
        entry = await self._journal_repo.create(
            user_id=user_id, text=text, source=source,
            practice_id=prompt.practice_id if prompt else None,
        )
        if prompt:
            await self._prompt_repo.mark_consumed(prompt.id)
        await self._session.commit()
        return CaptureResult(entry_id=entry.id, needs_assessment=prompt is not None
                             and prompt.kind == PromptKind.thought)
```

### LLM calls — tone and cost rules

Every LLM prompt pins the supportive tone and forbids criticism and unsolicited advice
(AC-13). Every call records usage (AC-16):

```python
text, usage = await self._llm_client.complete(prompt, max_tokens=220)
await self._usage_service.record(kind=UsageKind.analysis, model=self._model, usage=usage)
```

The clarify question for a missing self-assessment is one fixed localized phrase —
**no LLM in that flow** (AC-8).

---

## Repository pattern

Repositories are the only layer with `AsyncSession`. Use `flush()` + `refresh()`, never `commit()`.

```python
class JournalRepository:
    """CRUD access for JournalEntry records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: int, text: str, source: EntrySource,
                     practice_id: uuid.UUID | None) -> JournalEntry:
        """Create and flush a new entry; caller is responsible for commit."""
        entry = JournalEntry(user_id=user_id, text=text, source=source, practice_id=practice_id)
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry
```

---

## APScheduler job pattern (the project's central mechanism)

Deterministic scheduled deliveries are the heart of this bot. Conventions:

```python
def start_scheduler(bot: Bot, session_factory: async_sessionmaker, config: Config) -> AsyncIOScheduler:
    """Register the 60s tick and housekeeping jobs."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        tick, "interval", seconds=60,
        args=[bot, session_factory, config],
        max_instances=1,   # a slow tick must never overlap itself
        coalesce=True,     # missed minutes collapse into one re-evaluation
    )
    scheduler.start()
    return scheduler
```

- The tick reads the DB every run — **nothing is materialized at boot**, so data changes
  (practice rows, timezone) take effect on the next minute without restart (AC-4, AC-18).
- Idempotency is owned by us: claim a `(practice_id, slot_key)` row under a unique index
  before sending; insert-or-skip, never send-then-record.
- Slow work (the morning LLM analysis) is **never awaited inline in the tick** — enqueue it
  as a separate one-shot job (`max_instances=1`).
- Jobs open their own session from `session_factory` (no DI middleware outside aiogram).

---

## Result objects

Services return frozen dataclasses defined in the same file as the service:

```python
from dataclasses import dataclass
import uuid

@dataclass(frozen=True)
class CaptureResult:
    entry_id: uuid.UUID
    needs_assessment: bool
```

---

## Dependency injection

`DependencyMiddleware` in `bot/middleware.py` builds and injects all services per-request:

```python
async def __call__(self, handler, event, data):
    async with self._factory() as session:
        journal_repo = JournalRepository(session)
        prompt_repo = PendingPromptRepository(session)
        data["journal_service"] = JournalService(session, journal_repo, prompt_repo)

        # Optional — injected as None when credentials are missing
        if self._config.groq_api_key:
            data["transcription_service"] = TranscriptionService(self._config)
        else:
            data["transcription_service"] = None

        return await handler(event, data)
```

Handlers declare dependencies as keyword arguments — aiogram resolves them from `data`.

---

## Error handling

All domain exceptions are defined in `bot/exceptions.py`. Services raise them; handlers
catch them:

```python
try:
    result = await journal_service.capture(user_id, text, EntrySource.text)
except JournalCaptureError:
    await message.answer(t("capture_failed", lang))
    return
```

Raw exceptions must never reach the user. Log with context before re-raising.
A failed Telegram send (bad `file_id`) must be logged and visible — never swallowed silently.

---

## Comments policy

Write comments only where logic is non-obvious (workarounds, tricky algorithms, API quirks).
Every public function and class needs a one-line docstring (imperative mood, Google style).

---

## LLM API quirks

LLMs sometimes wrap JSON responses in markdown code fences (` ```json ... ``` `).
Always strip them before `json.loads()`:

```python
import re

text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
data = json.loads(text)
```
