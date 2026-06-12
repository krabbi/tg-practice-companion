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

_Filled by M0 (`users`) and onward (`practices`, `media_assets`, `practice_sends`,
`pending_prompts`, `journal_entries`, `self_assessments`, `morning_blessings`,
`motivational_images`, `daily_ai_analyses`, `api_usage_logs`, `want_list_items`,
`good_deeds`). One subsection per table with columns, indexes, and invariants._

## Dependency injection

_Filled by M0: `DependencyMiddleware` wiring — which services are built per-request,
which are optional (injected as `None` without credentials)._

## Scheduler

_Filled by M1: single 60s tick job, slot claiming via `practice_sends` unique index,
send-window convention `[06:00, 22:00)`, backward-tz-jump guard via `users.tz_changed_at`,
off-tick dispatch of the morning analysis job._

## Config reference

_Filled by M0: every `Config` field with type, default, and the env variable that sets it._

## Error handling

_Filled as domain exceptions appear in `bot/exceptions.py`: exception → where raised →
what the user sees._

## Cost accounting

_Filled by M3: `api_usage_logs`, per-model price table, month-to-date guardrail (AC-16),
per-run analysis cap $0.05 (AC-11)._
