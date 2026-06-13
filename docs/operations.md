# Операционный гайд

## Автономный разбор issues (Autobot)

Репозиторий настроен на автономную реализацию задач Claude-агентом
(см. issue #9): новые issues с меткой `claude-ready` подхватываются
автоматически, агент реализует задачу в отдельной ветке и открывает PR.
Человек нужен только чтобы проверить и смержить PR.

### Архитектура

- **`.github/workflows/claude-issue.yml`** — мгновенная реакция: срабатывает,
  когда issue открыт с меткой `claude-ready` или метка добавлена позже.
- **`.github/workflows/claude-sweeper.yml`** — швея: каждые 6 часов (и вручную
  через `workflow_dispatch`) подбирает накопившиеся `claude-ready`-issues по
  одному за запуск и реанимирует застрявшие.
- Оба воркфлоу делят `concurrency.group: claude-worker` — строго одна задача
  одновременно.
- Каждый запуск джоба — чистый контекст Claude. Очередь и идемпотентность —
  через метки.

### Протокол очереди (метки)

| Метка | Смысл |
|---|---|
| `claude-ready` | Opt-in: задача готова к автономной реализации. **Ставится оператором вручную** — без неё автоматика issue не трогает. |
| `claude-in-progress` | Замок очереди: агент ставит её первым действием, чтобы повторный/параллельный запуск не схватил тот же issue. |

- Готово = открытый PR с `Closes #N` (issue закроется сам при merge).
- Застрявшая задача: метка `claude-in-progress` висит больше суток, PR нет —
  швея снимет метку и возьмёт issue заново (или разберись вручную).
- Если issue непонятен, агент не выдумывает: задаёт уточняющие вопросы
  комментарием и снимает `claude-in-progress`.

### Разовая настройка (~30 минут, вручную)

1. **Claude GitHub App** — в любой сессии Claude Code выполнить
   `/install-github-app` (или вручную: <https://github.com/apps/claude> →
   установить на репозиторий).
2. **Подписочный токен** — локально выполнить `claude setup-token`, результат
   положить в секрет репозитория: Settings → Secrets and variables → Actions →
   `CLAUDE_CODE_OAUTH_TOKEN`.
3. **Self-hosted runner** (Mac/VPS/Raspberry Pi — машина должна быть включена):
   - Репозиторий → Settings → Actions → Runners → New self-hosted runner →
     выполнить выданные команды `./config.sh ...`;
   - поставить как сервис: `./svc.sh install && ./svc.sh start`;
   - на машине нужны `git`, Node, bash; входящие порты не нужны
     (раннер сам ходит к GitHub).
4. **Метки** `claude-ready` и `claude-in-progress` уже созданы в репозитории.

### Первый запуск

Сначала прогони автоматику на одном тестовом issue: поставь `claude-ready`,
запусти швею кнопкой (Actions → Claude sweeper → Run workflow), посмотри PR —
и только потом отпускай в автономку.

### Грабли

- **Раннер спит вместе с машиной.** Mac в сне = джобы висят в очереди до
  пробуждения. Для честной автономии — VPS за пару баксов или
  `caffeinate`/`pmset` на Mac.
- **Лимиты подписки.** При упоре в лимит джоб просто упадёт с ошибкой — это
  нормально, следующий запуск швеи повторит. Ничего настраивать не нужно.
- **Качество = качество постановки.** Критерии приёмки в тексте задачи
  окупаются сильнее любого тюнинга промпта — используй шаблон
  «Agent task» (`.github/ISSUE_TEMPLATE/agent-task.md`).
- **Не давай авто-merge.** Просмотр PR — единственное место, где участие
  человека реально нужно.

---

## Send-window boundary convention (M1)

The scheduler tick enforces a **half-open interval `[send_window_start, send_window_end)`**
in the user's local wall time.

| Boundary | Value (default) | Inclusive? | Notes |
|---|---|---|---|
| `send_window_start` | `6` (06:00) | **inclusive** — first valid slot | Configured via `SEND_WINDOW_START` env var |
| `send_window_end` | `22` (22:00) | **exclusive** — last valid slot is 21:59 | Configured via `SEND_WINDOW_END` env var |

### Rationale

The README states "06:00–22:00". This is interpreted as `[06:00, 22:00)`:
- A tick firing at **05:59** local is outside the window → no sends.
- A tick firing at **06:00** local is inside the window → sends proceed.
- A tick firing at **22:00** local is outside the window (exclusive upper bound) → no sends.
- A tick firing at **21:59** local is inside the window (last valid slot) → sends proceed.

### Practice configuration rule

Fixed-time practices (`fixed_times` cadence) **must** be configured with `schedule_times`
values strictly inside the window. Reference data:

| Practice | Time | Inside `[06:00, 22:00)`? |
|---|---|---|
| Morning blessing | `06:00` | Yes (inclusive lower bound) |
| Thought check-ins | `08:00`–`18:00` | Yes |
| Night hypnosis | `20:00` | Yes |

### Cadence phase is anchored to local midnight, not the send window

For `every_n_hours` practices, the phase is anchored via `anchor_hour` against local
midnight — **not** against `send_window_start`. Changing the send window only clips which
slots are admitted; it never moves a practice's phase.

Example: `interval_hours=4, anchor_hour=6` → due at local 02/06/10/14/18/22 every day.
With the default window `[06:00, 22:00)`, admitted slots are 06/10/14/18.
If the window is widened to `[05:00, 22:00)`, slot 02 is still not admitted (02 < 05),
and slot 06 is now admitted regardless — phase is unchanged.

### Seeding practices

Use `python -m cli.seed practices content/practices.yaml` to load or update practice rows.
The seed is idempotent (upserts by `name`). See `content/practices.example.yaml` for the
full YAML schema and the reference daily cycle.
