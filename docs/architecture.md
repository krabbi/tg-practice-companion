# Architecture — tg-practice-companion

> **Role:** living technical reference for the coder agent. Updated in the same PR as any
> change to DB schema, services, repositories, config, or the scheduler. The product
> baseline (frozen spec) is `README.md`; the data-model ontology there is the starting
> point for the schema designed here.

Sections are filled in as milestones M0–M6 are implemented.

---

## Layers

```
Handler (aiogram)  →  Service (business logic)  →  Repository (DB access)
```

See `CLAUDE.md` for the layer rules and `.claude/coding-patterns.md` for code patterns.

## DB schema

### `media_assets` (M1)

Owned media entity for audio/image practices. Stage 1 populates `telegram_file_id`; `storage_path` stays null until Stage 2 TMA upload flow.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `kind` | `Enum(audio, image)` | NO | — | Media type |
| `storage_path` | `String(512)` | YES | — | Object-store/filesystem path; null in Stage 1 |
| `telegram_file_id` | `String(256)` | YES | — | Stored Telegram file ID for re-sending (AC-2) |
| `mime` | `String(128)` | YES | — | MIME type, e.g. `audio/mpeg` |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |
| `updated_at` | `DateTime(tz=True)` | NO | `now()` | Last update timestamp |

Invariant: at least one of `storage_path` / `telegram_file_id` must be non-null (enforced at the service layer).

Migration: `alembic/versions/0002_practice_engine.py`

---

### `practices` (M1)

One row per schedulable practice. Cadence and content are data; code is the engine.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `name` | `String(120)` | NO | — | Human-readable identifier; used for idempotent seed upsert |
| `content_type` | `Enum(question, text, audio, image)` | NO | — | Determines delivery method |
| `content` | `Text` | YES | — | Body for `question`/`text` practices |
| `media_asset_id` | `UUID FK→media_assets` | YES | — | Set for `audio`/`image` practices |
| `periodicity_type` | `Enum(every_n_hours, fixed_times)` | NO | — | Cadence type |
| `interval_hours` | `Integer` | YES | — | Used with `every_n_hours` |
| `schedule_times` | `JSON` | YES | — | List of `"HH:MM"` strings for `fixed_times` |
| `anchor_hour` | `Integer` | YES | `0` | Phase anchor against local midnight |
| `anchor_minute` | `Integer` | YES | `0` | Minute offset within the anchor hour |
| `active` | `Boolean` | NO | `true` | Inactive rows are never evaluated |
| `start_date` | `DateTime` | YES | — | Practice not due before this date |
| `end_date` | `DateTime` | YES | — | Practice not due after this date |
| `sort_order` | `Integer` | NO | `0` | Display/delivery ordering |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |
| `updated_at` | `DateTime(tz=True)` | NO | `now()` | Last update timestamp |

Index: `ix_practices_active(active)`

---

### `practice_sends` (M1)

Idempotency dedup ledger. One row per `(practice_id, slot_key)` pair that has been successfully claimed and sent.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `practice_id` | `UUID FK→practices` | NO | — | CASCADE on delete |
| `user_id` | `BigInteger` | NO | — | Telegram user ID |
| `slot_key` | `String(40)` | NO | — | `"YYYY-MM-DDTHH:MM"` local wall-time string |
| `sent_at` | `DateTime(tz=True)` | NO | — | UTC instant of delivery |

Unique constraint: `uq_practice_send(practice_id, slot_key)` — the idempotency guard.

---

### `users` (M0)

One row per whitelisted Telegram user.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `telegram_id` | `BigInteger` | NO | — | Primary key; Telegram user ID |
| `timezone` | `String(64)` | YES | — | IANA timezone string, e.g. `"Europe/Minsk"`; null until first-run setup (M5) |
| `language` | `String(8)` | NO | `"ru"` | UI language code |
| `skip_until` | `Date` | YES | — | No practices sent until this date (AC-18 skip-day, M1) |
| `tz_changed_at` | `DateTime(tz=True)` | YES | — | UTC instant of last timezone change; consumed by the backward-jump guard (M1/M5) |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |
| `updated_at` | `DateTime(tz=True)` | NO | `now()` | Last update timestamp |

Migration: `alembic/versions/0001_initial_schema.py`

### `pending_prompts` (M2)

Durable binding anchor (Decision B1). One row per outgoing question; consumed by the user's reply.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `user_id` | `BigInteger` | NO | — | Telegram user ID |
| `practice_id` | `UUID FK→practices` | YES | — | SET NULL on practice delete |
| `kind` | `Enum(thought,good_deeds,want,other)` | NO | — | Determines whether a self-assessment is needed |
| `telegram_message_id` | `BigInteger` | YES | — | message_id of the outgoing bot message; used for precise reply binding |
| `consumed` | `Boolean` | NO | `false` | True once a reply has been bound and captured |
| `clarify_sent` | `Boolean` | NO | `false` | True once a clarify question has been sent for this prompt's entry |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Index: `ix_pending_prompts_user_consumed_created(user_id, consumed, created_at)`

Migration: `alembic/versions/0003_journal.py`

---

### `journal_entries` (M2)

One row per user reply (typed or transcribed voice). Raw audio bytes are never stored (AC-7).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `user_id` | `BigInteger` | NO | — | Telegram user ID |
| `practice_id` | `UUID FK→practices` | YES | — | SET NULL on practice delete; null when no prompt was bound |
| `text` | `Text` | NO | — | Typed message or Groq Whisper transcript |
| `source` | `Enum(text,voice)` | NO | — | Origin of the content |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Index: `ix_journal_entries_user_created(user_id, created_at)`

Migration: `alembic/versions/0003_journal.py`

---

### `self_assessments` (M2)

One-to-one with `journal_entries`. Records whether the user believes a thought leads to their goals (AC-8). No LLM is used in this flow.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `journal_entry_id` | `UUID FK→journal_entries` | NO | — | CASCADE on delete; unique |
| `leads_to_goals` | `Boolean` | NO | — | User's self-assessment answer |
| `set_via` | `Enum(button,clarify)` | NO | — | How the assessment was recorded |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Unique constraint: `uq_self_assessment_entry(journal_entry_id)`

Migration: `alembic/versions/0003_journal.py`

---

_Further tables (`morning_blessings`, `motivational_images`,
`daily_ai_analyses`, `api_usage_logs`, `want_list_items`, `good_deeds`) added by
M3–M6 milestones._

## Dependency injection

### M0 wiring

`bot/bot.py::create_dispatcher` wires all middleware and routers at startup:

1. `AuthMiddleware(config.allowed_user_ids)` — registered as `dp.update.outer_middleware`;
   drops updates from non-whitelisted users before any handler runs.
2. `commands.router` — first registered router; handles `/start` and `/help`.

Router registration order is load-bearing: the commands router must come before the
catch-all journal router (M2) so that `/start` and `/help` are matched first.

### M1 additions

`create_dispatcher` now accepts an optional `session_factory` parameter. When provided:

3. `DependencyMiddleware(session_factory, config)` — registered as `dp.update.middleware`;
   opens one `AsyncSession` per update, builds all repositories and services, injects them
   into the handler `data` dict, then closes the session after the handler returns.
4. `skip_day.router` — registered after `commands.router`; handles `/skip_day` and the
   `skip_day:confirm` inline callback.

### M2 additions

Router registration order is load-bearing (issue #4 Decision B1). Canonical order:

1. `commands.router` — `/start`, `/help`
2. *(slot reserved for `timezone_setup` FSM router — M5)*
3. `assessment.router` — `assess:<id>:yes|no` callback queries
4. `skip_day.router` — `/skip_day` command and `skip_day:confirm` callback
5. `journal.router` — `F.text` / `F.voice` catch-all with `StateFilter(None)` (last)

The journal catch-all carries `StateFilter(None)` so it yields whenever an FSM state is active (e.g. first-run timezone setup in M5).

`DeliveryService` now accepts an optional `prompt_repo: PendingPromptRepository` parameter. When provided (the scheduler always provides it), every outgoing `question` practice writes a `pending_prompt` row capturing the Telegram `message_id`. The scheduler commits after successful delivery to persist the row.

`TranscriptionService` is injected as `None` when `config.groq_api_key` is empty; handlers guard with `if transcription_service is None`.

### Services (M1 + M2)

| Service | File | Responsibility |
|---|---|---|
| `PracticeService` | `bot/services/practice_service.py` | Active practice queries, `due_now` evaluation |
| `DeliveryService` | `bot/services/delivery_service.py` | Renders and sends a practice; writes `pending_prompt` for `question` practices |
| `TimezoneService` | `bot/services/timezone_service.py` | Validate IANA timezone, persist, stamp `tz_changed_at` |
| `SkipDayService` | `bot/services/skip_day_service.py` | Set `skip_until = local today`, commit |
| `JournalService` | `bot/services/journal_service.py` | Capture replies: resolve binding, create `JournalEntry`, consume prompt |
| `AssessmentService` | `bot/services/assessment_service.py` | Record `SelfAssessment`; `needs_clarify` guard for the sweep |
| `TranscriptionService` | `bot/services/transcription_service.py` | Groq Whisper transcription; optional (None when key absent) |

### Repositories (M1 + M2)

| Repository | File | Responsibility |
|---|---|---|
| `UserRepository` | `bot/repositories/user_repository.py` | User CRUD; `get_first`, `get_by_telegram_id`, `save` |
| `PracticeRepository` | `bot/repositories/practice_repository.py` | Practice + MediaAsset CRUD; `get_active_practices`, `get_by_name` |
| `PracticeSendRepository` | `bot/repositories/practice_send_repository.py` | `try_claim` (insert-or-skip), `prune_older_than` |
| `PendingPromptRepository` | `bot/repositories/pending_prompt_repository.py` | `create`, `get_by_telegram_message_id`, `newest_unconsumed`, `mark_consumed`, `mark_clarify_sent` |
| `JournalRepository` | `bot/repositories/journal_repository.py` | `create`, `get_by_id` |
| `SelfAssessmentRepository` | `bot/repositories/self_assessment_repository.py` | `create`, `get_by_entry_id` |

## Scheduler (M1)

`bot/scheduler.py` — `start_scheduler(bot, session_factory, config)` registers two APScheduler jobs:

### `practice_tick` (every 60 seconds)

- `max_instances=1`, `coalesce=True`: a slow tick can never overlap itself; a missed minute collapses into one re-evaluation (no catch-up — spec-correct per README).
- Reads the DB every run — nothing is materialized at boot. Data changes (new practice rows, timezone edits) take effect on the next minute without restart (AC-4, AC-18).
- Flow per tick:
  1. `now_utc = datetime.now(UTC)` → resolve user's local timezone → `local_now`.
  2. Short-circuit if outside the send window `[send_window_start, send_window_end)`.
  3. Short-circuit if `user.skip_until >= local_now.date()` (AC-5).
  4. `practice_service.due_now(local_now)` → list of due practices.
  5. For each practice: compute `slot_key = "YYYY-MM-DDTHH:MM"` → apply backward-tz-jump guard → `practice_send_repository.try_claim(...)` (insert-or-skip on unique index) → if claimed, **first commit** (persists the claim), then `delivery_service.send(practice, user)` (writes `pending_prompt` for `question` practices via flush), then **second commit** (persists the `pending_prompt`).

### Send-window convention

Half-open interval `[send_window_start, send_window_end)` in local wall time. Defaults: `06 ≤ hour < 22`. The `22:00` boundary is **exclusive** — last possible slot is `21:59`. See `docs/operations.md` for the full specification and rationale.

### Backward-tz-jump guard

Before claiming a slot, the tick converts `user.tz_changed_at` (UTC) into the current zone and refuses to claim any slot whose local wall-time precedes that instant. This prevents westward timezone jumps from replaying already-passed slots. Forward jumps skip slots with no catch-up.

### Morning analysis dispatch seam

The once-daily morning LLM analysis is never awaited inline inside `tick`. When due (M3), `tick` enqueues it as a separate one-shot APScheduler job (`run_morning_analysis`, `max_instances=1`). The dispatch seam is wired here; the job body lands in M3.

### `housekeeping` (daily at 03:00 UTC)

Prunes `practice_sends` rows older than 14 days to keep the ledger table bounded.

## Config reference

All fields are loaded from environment variables (or `.env` file) via `pydantic-settings`.

| Field | Env var | Type | Default | Notes |
|---|---|---|---|---|
| `telegram_bot_token` | `TELEGRAM_BOT_TOKEN` | `str` | required | Bot API token from @BotFather |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | `str` | required | Anthropic API key |
| `groq_api_key` | `GROQ_API_KEY` | `str` | `""` | Empty string disables voice transcription |
| `database_url` | `DATABASE_URL` | `str` | required | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://...` |
| `allowed_user_ids` | `ALLOWED_USER_IDS` | `list[int]` | required | CSV of Telegram user IDs; exactly one in practice |
| `monthly_cost_limit_usd` | `MONTHLY_COST_LIMIT_USD` | `float` | `10.0` | Monthly API spend cap (AC-16) |
| `analysis_cost_cap_usd` | `ANALYSIS_COST_CAP_USD` | `float` | `0.05` | Per-run morning analysis cap (AC-11) |
| `llm_model` | `LLM_MODEL` | `str` | `"claude-haiku-4-5-20251001"` | Pinned Anthropic model |
| `whisper_model` | `WHISPER_MODEL` | `str` | `"whisper-large-v3-turbo"` | Pinned Groq Whisper model |
| `default_language` | `DEFAULT_LANGUAGE` | `str` | `"ru"` | Bot UI language |
| `send_window_start` | `SEND_WINDOW_START` | `int` | `6` | Start of send window (local hour, inclusive) |
| `send_window_end` | `SEND_WINDOW_END` | `int` | `22` | End of send window (local hour, exclusive) |
| `jwt_secret` | `JWT_SECRET` | `str` | `""` | Stage-2 stub; unused in Stage 1 |
| `cors_origins` | `CORS_ORIGINS` | `list[str]` | `[]` | Stage-2 stub; unused in Stage 1 |

## CI / test environment variables

| Env var | Where used | Notes |
|---|---|---|
| `TEST_DATABASE_URL` | `tests/integration/test_migrations.py` | Async SQLAlchemy URL for a real Postgres 16 instance. Set by the CI workflow's service container. When absent the migration tests are skipped automatically. Never set in production. |

## Error handling

All domain exceptions extend `PracticeCompanionError` in `bot/exceptions.py`.

| Exception | Where raised | User sees |
|---|---|---|
| `TimezoneError` | `TimezoneService` | — (internal, M5) |
| `DeliveryError` | `DeliveryService` | `t("delivery_error")` |
| `MediaAssetError` | `DeliveryService._resolve_telegram_file_id` | logged, `DeliveryError` re-raised |
| `JournalCaptureError` | `JournalService.capture` | `t("capture_failed")` |
| `AssessmentError` | `AssessmentService.record` | `t("assessment_already_set")` |

## Cost accounting

_Filled by M3: `api_usage_logs`, per-model price table, month-to-date guardrail (AC-16),
per-run analysis cap $0.05 (AC-11)._
