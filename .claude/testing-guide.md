# Testing Guide — tg-practice-companion

Detailed testing conventions. Read this when writing tests.
For the quick summary see `CLAUDE.md`.

---

## Structure

Test file mirrors source file:
```
bot/services/journal_service.py   →  tests/unit/test_journal_service.py
bot/repositories/journal.py       →  tests/unit/test_journal_repository.py
```

---

## Bootstrap conftest (current state — read before assuming fixtures)

While the `bot/` package has no real modules, `tests/conftest.py` is **self-contained**:

- `fake_config` is a stub dataclass defined **inside conftest.py** — it does NOT import
  `bot.config`. Once `bot/config.py` lands (M0), conftest switches to constructing the
  real `Config` (sibling pattern) and the stub is removed.
- The `db_session` fixture is **deliberately absent** until `bot/models` exists. Add it
  together with the first models (aiosqlite `:memory:`, create_all/drop_all per test).
- The coverage gate (≥ 80%) activates once `bot/` has real modules; until then coder and
  pr-reviewer skip coverage commands (bootstrap bypass).

---

## Unit tests (`tests/unit/`)

Mock all external dependencies. Fast — no I/O, no network.

```python
async def test_capture_binds_newest_prompt() -> None:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    repo = MagicMock(spec=JournalRepository)
    repo.create = AsyncMock(return_value=mock_entry)
    svc = JournalService(session=session, journal_repo=repo, prompt_repo=prompt_repo)

    result = await svc.capture(user_id=1, text="мысль", source=EntrySource.text)

    repo.create.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert result.needs_assessment is True
```

### Service test factory pattern

When a service has many tests, use a `make_service()` factory to avoid repetition:

```python
def make_service() -> tuple[JournalService, MagicMock, MagicMock]:
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    repo = MagicMock(spec=JournalRepository)
    svc = JournalService(session=session, journal_repo=repo, prompt_repo=MagicMock())
    return svc, repo, session
```

### Mocking LLM and transcription clients

```python
mock_llm = MagicMock(spec=LlmClient)
mock_llm.complete = AsyncMock(return_value=("supportive text", usage_stub))

mock_transcription = MagicMock(spec=TranscriptionService)
mock_transcription.transcribe = AsyncMock(return_value="расшифровка")
```

Tests that assert "no LLM in this flow" (the deterministic clarify, AC-8) must assert
`mock_llm.complete.assert_not_awaited()`.

### Scheduler tests — frozen clock

Time-dependent logic (`due_now`, send window, slot keys) takes `local_now` as an argument —
pass a fixed `datetime` in tests; never call `datetime.now()` deep inside logic under test.

---

## Integration tests (`tests/integration/`)

Test the **Service → Repository** chain against in-memory SQLite.
Use the `db_session` fixture (once it exists — see bootstrap note above). External APIs
still mocked. Migration tests (`test_migrations.py`) run against real Postgres 16 via a
GitHub Actions service container (engine-specific types: Enum, JSON, Numeric, tz-aware
DateTime); SQLite shims are documented in `tests/conftest.py` when they appear.

---

## Rules

- `asyncio_mode = "auto"` is set in `pyproject.toml` — all async tests run automatically.
- Use `fake_config` (and later `db_session`) fixtures from `tests/conftest.py`.
- Use `MagicMock(spec=ClassName)` — the `spec` catches attribute typos at test time.
- Use `AsyncMock` for all `async def` methods.
- Never use real API keys, tokens, or production DB in tests.
- Coverage target: **≥ 80%** on all new code (once `bot/` exists). Run with `make coverage`.
- `make test` for quick iteration (no coverage threshold); CI uses the same bootstrap-skip
  logic as the agents.

---

## Running tests

```bash
make test        # fast, no coverage threshold
make coverage    # with --cov, fails if < 80% (meaningful once bot/ has modules)
pytest tests/unit/test_foo.py -v   # single file
pytest -k "test_name" -v           # single test
pytest --collect-only              # sanity: conftest imports cleanly (bootstrap check)
```
