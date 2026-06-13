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

_Further tables (`practices`, `media_assets`, `practice_sends`, `pending_prompts`,
`journal_entries`, `self_assessments`, `morning_blessings`, `motivational_images`,
`daily_ai_analyses`, `api_usage_logs`, `want_list_items`, `good_deeds`) added by
M1–M6 milestones._

## Dependency injection

### M0 wiring

`bot/bot.py::create_dispatcher` wires all middleware and routers at startup:

1. `AuthMiddleware(config.allowed_user_ids)` — registered as `dp.update.outer_middleware`;
   drops updates from non-whitelisted users before any handler runs.
2. `commands.router` — first registered router; handles `/start` and `/help`.

Router registration order is load-bearing: the commands router must come before the
catch-all journal router (M2) so that `/start` and `/help` are matched first.

_`DependencyMiddleware` (per-request session + service injection) is added in M1 when
the first service layer lands._

## Scheduler

_Filled by M1: single 60s tick job, slot claiming via `practice_sends` unique index,
send-window convention `[06:00, 22:00)`, backward-tz-jump guard via `users.tz_changed_at`,
off-tick dispatch of the morning analysis job._

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

## Error handling

_Filled as domain exceptions appear in `bot/exceptions.py`: exception → where raised →
what the user sees._

## Cost accounting

_Filled by M3: `api_usage_logs`, per-model price table, month-to-date guardrail (AC-16),
per-run analysis cap $0.05 (AC-11)._
