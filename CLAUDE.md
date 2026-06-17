# CLAUDE.md — Project Guide

This file is always loaded. It covers what every agent needs to know upfront.
Detailed coding patterns and testing conventions are in `.claude/` — load them when you need them.

---

## Project overview

`tg-practice-companion` is a personal Telegram bot for one user that guides her through a
daily program of CBT practices: scheduled blessings, thought-registration questions, practice
reminders, night hypnosis audio, motivational images; it records every reply (text and voice)
into a long-term journal with a "does this thought lead to my goals" self-assessment, and sends
a supportive AI analysis of yesterday every morning.

**Stack:** Python 3.11+, aiogram 3.x, SQLAlchemy async + Alembic, APScheduler,
Anthropic API (Haiku-class), Groq Whisper API, Docker Compose. Web admin SPA:
Vue 3 + Vite + TypeScript (vue-router, Pinia) in `frontend/`.

**Core abstraction:** a **Practice** is data, code is the engine. A practice row defines
content type (question / text / audio / image), content or media ref, cadence, and lifetime.
Changing the practice set or schedule is a data change — never a code change.

---

## Sources of truth

| Document | Role |
|---|---|
| `README.md` | **Frozen product baseline** (ТЗ, AC-1..AC-22). Read-only — never updated by feature PRs. |
| `docs/user_guide.md` | **Living product doc.** User-facing changes are documented here from PR #1. |
| `docs/architecture.md` | Living technical reference: DB schema, DI wiring, scheduler, config. |

---

## Architecture

Three strict layers — never skip or cross them:

```
Handler (aiogram)  →  Service (business logic)  →  Repository (DB access)
```

- **Handlers** — thin: call services, reply to user. No logic, no DB, no external APIs.
- **Services** — all business logic. Own transaction boundaries (`commit()`). No Telegram calls.
- **Repositories** — only layer with `AsyncSession`. Use `flush()`, never `commit()`.

For code examples and patterns → **read `.claude/coding-patterns.md`**.

---

## Code style

| Tool | Config |
|---|---|
| Formatter | `ruff format` (line length 100) |
| Linter | `ruff check` rules: E, F, I, UP, B, SIM |
| Type hints | Required on all function signatures |
| Python version | 3.11+ (`X \| Y`, `match`, etc.) |

```bash
make format    # ruff format .
make lint      # ruff check .
make coverage  # pytest --cov + per-file gate; fails if ANY bot/ file < 80%
```

**Gate honesty:** the ruff gate is active from day one. The test/coverage gate (≥ 80% **per
file**) activates once the `bot/` package has real modules — until then coder and pr-reviewer
skip coverage commands entirely (bootstrap bypass, see the agent files).

The per-file gate is enforced by `scripts/check_coverage.py` (parses `coverage.json`,
exits non-zero if any `bot/` file is below 80%). Both the overall ≥ 80% threshold
(`--cov-fail-under=80`) and the per-file gate run together in `make coverage` and CI.

---

## Language policy

All artifacts (issues, PR descriptions, code comments, docstrings, git commits) — **English**.
Product docs (`README.md`, `docs/user_guide.md`) — **Russian**. Respond to the operator in
the language they write in. All user-facing bot strings go through the i18n layer (`ru`
primary, `en` canonical fallback) — never hardcode UI strings (AC-14).

---

## Commit convention

Follow [Conventional Commits](https://www.conventionalcommits.org/). Reference the issue number.

| Prefix | When |
|--------|------|
| `feat:` | New feature or user-visible behaviour |
| `fix:` | Bug fix |
| `refactor:` | No behaviour change |
| `test:` | Tests only |
| `docs:` | Documentation only |
| `chore:` | Tooling, config, dependencies |

Example: `feat: add skip-day command (#23)`

---

## Documentation — update rules

When your change affects any of the following, update the corresponding file **in the same PR**:

| What changed | File to update |
|---|---|
| New/changed user-facing command, button, or flow | `docs/user_guide.md` |
| New service, repository, model, config variable, DB schema | `docs/architecture.md` |
| New Alembic migration | `docs/architecture.md` (DB schema section) |
| New env variable | `docs/architecture.md` (config section) |
| Coding convention or DI wiring change | `.claude/coding-patterns.md` + `CLAUDE.md` |
| Testing convention change | `.claude/testing-guide.md` |

`README.md` never appears in this table — it is the frozen baseline.

---

## Project-specific guardrails

- **CBT tone (AC-13):** every LLM prompt pins a supportive tone and forbids criticism and
  unsolicited advice. The clarify question for missing self-assessment is one fixed localized
  phrase — no LLM in that flow (AC-8).
- **Cost logging (AC-16):** every product LLM/API call records tokens and cost
  (`api_usage_logs`); the morning analysis must cost ≤ $0.05 per run (AC-11).
- **Send window:** 06:00–22:00 local, half-open `[06:00, 22:00)`. No catch-up for missed
  check-ins. All schedules live in the user's local timezone (AC-18).

---

## Detail files — load when needed

| File | When to read |
|---|---|
| `.claude/coding-patterns.md` | Before writing any handler, service, repository, or model |
| `.claude/testing-guide.md` | Before writing tests |
| `.claude/orchestration.md` | Orchestrating the multi-agent pipeline / reviewing / merging — NOT needed to implement a single issue |
| `docs/architecture.md` | For DB schema, DI wiring, scheduler, config reference |
| `docs/user_guide.md` | For user-facing behaviour, commands, flows |

### Do NOT read

- `.omc/` — planning/state artifacts of the orchestration tooling. Plans live there for the
  operator; agents get their task from the GitHub issue, not from `.omc/`.
- `.understand-anything/` — generated knowledge-graph artifacts (if present). Large,
  low-signal-per-token, goes stale.

---

## File layout

Top-level only — filled in as implemented (greenfield):

```
bot/            # entry point, config, db, i18n, middleware, scheduler
  handlers/     # thin aiogram handlers
  services/     # business logic
  repositories/ # DB access
  models/       # SQLAlchemy models
  middlewares/  # auth whitelist
web/            # FastAPI web-admin backend (app factory, routers, auth, deps)
frontend/       # Vue 3 + Vite + TS web-admin SPA (src/api, src/stores, views)
cli/            # operator seeding commands
alembic/        # migrations
content/        # operator-loaded practice content (YAML)
tests/          # unit/ + integration/, conftest.py
docs/           # user_guide.md, architecture.md, operations.md
.claude/        # agents/, commands/, coding-patterns.md, testing-guide.md, orchestration.md
```

**Frontend (`frontend/`) gates:** `typecheck`, `test` (Vitest), and `build` are mandatory and run
in CI (job `frontend`); `lint` (ESLint) is recommended. Frontend unit tests are **required**, but
the SPA has **no numeric coverage gate** — the per-file ≥80% gate is Python-only; the pr-reviewer
judges whether frontend tests are adequate.
