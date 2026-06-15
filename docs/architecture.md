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
| `content_type` | `Enum(question, text, audio, image, want)` | NO | — | Determines delivery method |
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

Migrations: `alembic/versions/0002_practice_engine.py` (initial schema); `alembic/versions/0007_want_practice_type.py` (added `want` to the `content_type` enum).

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
| `last_blessing_date` | `Date` | YES | — | Date morning blessing was last sent; daily dedup guard (M3.4) |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |
| `updated_at` | `DateTime(tz=True)` | NO | `now()` | Last update timestamp |

Migrations: `alembic/versions/0001_initial_schema.py` (initial columns); `alembic/versions/0005_user_blessing_date.py` (added `last_blessing_date`).

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

### `morning_blessings` (M3)

A pool of short blessing texts cycled each morning in `rotation_order` sequence.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `text` | `Text` | NO | — | Blessing body |
| `rotation_order` | `Integer` | NO | — | Ascending delivery order |
| `active` | `Boolean` | NO | `true` | Inactive rows are skipped |

Unique constraint: `uq_morning_blessings_rotation_order(rotation_order)`

Migration: `alembic/versions/0004_morning_and_usage.py`

---

### `motivational_images` (M3)

A pool of motivational images, each backed by a `MediaAsset`.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `media_asset_id` | `UUID FK→media_assets` | NO | — | The underlying media asset |
| `active` | `Boolean` | NO | `true` | Inactive rows are skipped |

Migration: `alembic/versions/0004_morning_and_usage.py`

---

### `daily_ai_analyses` (M3)

Stores the AI-generated morning analysis message for each user per calendar day.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `user_id` | `BigInteger` | NO | — | Telegram user ID |
| `analysis_date` | `Date` | NO | — | Local calendar date the analysis covers |
| `n_total` | `Integer` | NO | — | Total journal entries analysed |
| `n_leads` | `Integer` | NO | — | Entries the user marked as leading to goals |
| `message` | `Text` | NO | — | LLM-generated analysis text sent to the user |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Unique constraint: `uq_daily_analysis_user_date(user_id, analysis_date)` — at most one analysis per user per day.

Migration: `alembic/versions/0004_morning_and_usage.py`

---

### `api_usage_logs` (M3)

One row per product LLM/API call for cost tracking (AC-16).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | NO | `uuid4()` | Primary key |
| `kind` | `Enum(analysis, report, transcription)` | NO | — | Type of API call |
| `model` | `String(64)` | NO | — | Model identifier, e.g. `claude-haiku-4-5-20251001` |
| `input_tokens` | `Integer` | NO | — | Prompt tokens consumed |
| `output_tokens` | `Integer` | NO | — | Completion tokens generated |
| `audio_seconds` | `Float` | YES | — | Audio duration for `transcription` calls; null otherwise |
| `cost_usd` | `Numeric(10,6)` | NO | — | Computed cost in USD |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Index: `ix_api_usage_logs_created_at(created_at)` — supports period-sum queries (AC-16 monthly cap).

Migration: `alembic/versions/0004_morning_and_usage.py`

---

### want_list_items

Stores the user's want-list entries. Created by M4.1.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `user_id` | `BigInteger` | NO | — | Telegram user id |
| `text` | `Text` | NO | — | Item description |
| `done` | `Boolean` | NO | `false` | Checked-off flag |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Migration: `alembic/versions/0006_lists.py`

---

### good_deeds

Stores per-date good deed records. Created by M4.1.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `uuid4()` | PK |
| `user_id` | `BigInteger` | NO | — | Telegram user id |
| `text` | `Text` | NO | — | Deed description |
| `deed_date` | `Date` | NO | — | The date the deed was performed |
| `created_at` | `DateTime(tz=True)` | NO | `now()` | Row creation timestamp |

Index: `ix_good_deeds_user_id_deed_date(user_id, deed_date)` — supports per-user per-day queries.

Migration: `alembic/versions/0006_lists.py`

---

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
| `LlmClient` | `bot/services/llm_client.py` | Anthropic Messages API wrapper; returns `(text, usage)` for cost recording |
| `UsageService` | `bot/services/usage_service.py` | Record `ApiUsageLog` rows; compute `month_to_date_cost()` for the guardrail (AC-16) |
| `AnalysisService` | `bot/services/analysis_service.py` | Build the once-daily morning AI analysis: query stats, enforce cost guardrail, call LLM with supportive AC-13 prompt, persist `DailyAiAnalysis` row (AC-11, AC-16) |
| `BlessingService` | `bot/services/blessing_service.py` | Select today's morning blessing by date-derived round-robin (`today.toordinal() % count`); idempotent for the same date (AC-3) |
| `WantListService` | `bot/services/want_list_service.py` | Add want-list items (`add`), list active (undone) items (`list_active`), pick a random undone item (`random_active`) |

### Repositories (M1 + M2 + M3)

| Repository | File | Responsibility |
|---|---|---|
| `UserRepository` | `bot/repositories/user_repository.py` | User CRUD; `get_first`, `get_by_telegram_id`, `save` |
| `PracticeRepository` | `bot/repositories/practice_repository.py` | Practice + MediaAsset CRUD; `get_active_practices`, `get_by_name` |
| `PracticeSendRepository` | `bot/repositories/practice_send_repository.py` | `try_claim` (insert-or-skip), `prune_older_than` |
| `PendingPromptRepository` | `bot/repositories/pending_prompt_repository.py` | `create`, `get_by_telegram_message_id`, `newest_unconsumed`, `mark_consumed`, `mark_clarify_sent` |
| `JournalRepository` | `bot/repositories/journal_repository.py` | `create`, `get_by_id`, `daily_stats(user_id, date)` → `DailyStats(n_total, n_leads)` |
| `SelfAssessmentRepository` | `bot/repositories/self_assessment_repository.py` | `create`, `get_by_entry_id` |
| `BlessingRepository` | `bot/repositories/blessing_repository.py` | `save`, `get_by_id`, `get_active_ordered` |
| `ImageRepository` | `bot/repositories/image_repository.py` | `save`, `get_by_id`, `get_active` |
| `AnalysisRepository` | `bot/repositories/analysis_repository.py` | `save`, `get_by_id`, `get_by_user_and_date` |
| `ApiUsageRepository` | `bot/repositories/api_usage_repository.py` | `save`, `get_by_id`, `sum_cost_since` |
| `WantListRepository` | `bot/repositories/want_list_repository.py` | `create` (insert item), `get_by_id`, `list_for_user` (all items for a user, oldest first), `mark_done`, `delete` |

## Scheduler (M1)

`bot/scheduler.py` — `start_scheduler(bot, session_factory, config)` registers two APScheduler jobs:

### `practice_tick` (every 60 seconds)

- `max_instances=1`, `coalesce=True`: a slow tick can never overlap itself; a missed minute collapses into one re-evaluation (no catch-up — spec-correct per README).
- Reads the DB every run — nothing is materialized at boot. Data changes (new practice rows, timezone edits) take effect on the next minute without restart (AC-4, AC-18).
- Flow per tick:
  1. `now_utc = datetime.now(UTC)` → resolve user's local timezone → `local_now`.
  2. If `local_now.hour == _MORNING_BLOCK_HOUR` and `minute == 0`: dispatch `run_morning_analysis` as a one-shot APScheduler job (before the send-window check, so the analysis always fires regardless of send-window reconfiguration).
  3. Short-circuit if outside the send window `[send_window_start, send_window_end)`.
  4. Short-circuit if `user.skip_until >= local_now.date()` (AC-5).
  5. If `local_now.hour == _MORNING_BLOCK_HOUR` and `minute == 0` and `user.last_blessing_date != today`: call `BlessingService.for_date(today)` → if a blessing is found, set `user.last_blessing_date = today`, **commit** (claim before send), then `bot.send_message(blessing.text)`.
  6. `practice_service.due_now(local_now)` → list of due practices.
  7. Sort due practices with `compose()` (ascending `sort_order`).
  8. For each practice: compute `slot_key = "YYYY-MM-DDTHH:MM"` → apply backward-tz-jump guard → `practice_send_repository.try_claim(...)` (insert-or-skip on unique index) → if claimed, **first commit** (persists the claim), then branch on `content_type`: for `want`, call `WantListService.random_active(user_id)` — if an undone item exists, send it via `bot.send_message`; if the list is empty, the slot is claimed silently. For all other types, call `delivery_service.send(practice, user)` (writes `pending_prompt` for `question` practices via flush), then **second commit** (persists the `pending_prompt`).

### Send-window convention

Half-open interval `[send_window_start, send_window_end)` in local wall time. Defaults: `06 ≤ hour < 22`. The `22:00` boundary is **exclusive** — last possible slot is `21:59`. See `docs/operations.md` for the full specification and rationale.

### Backward-tz-jump guard

Before claiming a slot, the tick converts `user.tz_changed_at` (UTC) into the current zone and refuses to claim any slot whose local wall-time precedes that instant. This prevents westward timezone jumps from replaying already-passed slots. Forward jumps skip slots with no catch-up.

### Morning block (06:00)

At `_MORNING_BLOCK_HOUR` (06:00) local time, the tick fires three sequential steps:

1. **Analysis dispatch (before send-window check):** `run_morning_analysis` is enqueued as a separate one-shot APScheduler job (`max_instances=1`, `replace_existing=True`). The job is dispatched before the send-window guard so the AI analysis always fires even if the send window is reconfigured to start after 06:00. The job opens its own session, resolves yesterday's date in the user's local timezone, builds `AnalysisService`, and calls `AnalysisService.build(user_id, analysis_date, lang)`. The service is idempotent per `(user_id, analysis_date)` so concurrent dispatches are safe. After `build` returns, the job sends `result.message` via `bot.send_message`; send failures are logged but do not raise (the analysis row is already persisted).

2. **Blessing rotation (after send-window check, before practice loop):** `BlessingService.for_date(today)` selects the active blessing using `today.toordinal() % len(active_blessings)`, advancing round-robin through blessings sorted by `rotation_order`. Idempotency is enforced by `user.last_blessing_date`: the tick only sends a blessing when `last_blessing_date != today`. The claim (`user.last_blessing_date = today`) is committed **before** `bot.send_message` so a bot restart at :00 never double-sends (consistent with the practice claim-before-send pattern). Send failures are logged and do not un-claim the date.

3. **Practice delivery:** `practice_service.due_now(local_now)` returns the due practices, sorted by `compose()` (`sort_order` ascending). The reference ordering from `content/practices.yaml`: morning practice (sort_order ≤ 30), motivational image (sort_order ≤ 40), hourly questions (sort_order ≥ 100, after the morning block). Each practice goes through the backward-tz-jump guard and `try_claim` idempotency check before delivery.

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

## CI automation (Autobot v2)

The repository uses a 7-workflow label-driven pipeline (`feat/autobot-v2-pipeline`, issue #36)
that runs the full implement-task cycle autonomously in GitHub Actions:

```
claude-issue / claude-sweeper  →  claude-pr-review  →  claude-pr-fix (up to 5 rounds)
  →  claude-pr-product-review  →  claude-pr-product-fix (up to 5 rounds)
  →  claude-pr-merge
```

All worker jobs share `concurrency: group: claude-worker`. Routing is done via PR/issue
labels using the fine-grained PAT secret `AUTOMATION_TOKEN`. The merge gate requires
named check runs `lint` AND `test` to have conclusion `success`; `skipped`/`neutral`
(e.g. `build-push` on PRs) are non-blocking. Full operational details and the dry-run
procedure are in `docs/operations.md` → "Autobot v2" section.

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

Every product LLM/API call records a row in `api_usage_logs` (AC-16).

### Price table (`bot/services/usage_service.py`)

| Model | Input (per token) | Output (per token) | Source |
|---|---|---|---|
| `claude-haiku-4-5-20251001` | $0.0000008 ($0.80/1M) | $0.000004 ($4.00/1M) | Anthropic pricing 2025-10 |

Groq Whisper: $0.111/hour ≈ $3.083×10⁻⁵/second.

### Guardrails

| Guardrail | Config field | Default | Enforced by |
|---|---|---|---|
| Monthly spend cap | `monthly_cost_limit_usd` | `$10.00` | `UsageService.month_to_date_cost()` checked in `analysis_service` |
| Per-run analysis cap | `analysis_cost_cap_usd` | `$0.05` | checked before each morning analysis LLM call (AC-11) |

A Haiku call with ~1000 input + 220 output tokens costs ≈ $0.0017, well under the $0.05 per-run cap.

### Recording usage

```python
# LLM call
text, usage = await self._llm_client.complete(system=..., user=..., max_tokens=220)
await self._usage_service.record(kind=UsageKind.analysis, model=self._llm_client.model, usage=usage)
await self._session.commit()

# Transcription call
transcript = await transcription_service.transcribe(audio_bytes)
await usage_service.record(kind=UsageKind.transcription, model="whisper-large-v3-turbo", audio_seconds=duration)
```
