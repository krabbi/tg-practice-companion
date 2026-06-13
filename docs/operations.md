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
- Оба воркфлоу крутятся на **GitHub-hosted runner** (`ubuntu-latest`) — отдельную
  машину поднимать не нужно. Приватный репо даёт 2000 бесплатных минут Actions в
  месяц; при 20–40 мин на задачу это 50–100 задач/мес. Реальный потолок — не
  минуты, а лимит Pro-подписки (его жжёт сам агент). Если задач станет реально
  много (упор в 2000 мин) — переведи `runs-on` обратно на `self-hosted`.
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
3. **Runner** — не требуется: воркфлоу используют GitHub-hosted `ubuntu-latest`.
   Если задач станет так много, что упрёшься в 2000 мин/мес, переведи `runs-on`
   обратно на `self-hosted` и подними свою машину (Settings → Actions → Runners
   → New self-hosted runner → `./config.sh ...`, затем `./svc.sh install && ./svc.sh start`).
4. **Метки** `claude-ready` и `claude-in-progress` уже созданы в репозитории.

### Первый запуск

Сначала прогони автоматику на одном тестовом issue: поставь `claude-ready`,
запусти швею кнопкой (Actions → Claude sweeper → Run workflow), посмотри PR —
и только потом отпускай в автономку.

### Грабли

- **Минуты Actions.** GitHub-hosted раннер ест бесплатные минуты (2000/мес на
  приватном репо). Остаток виден в Settings → Billing and licensing → Plans and
  usage. Для текущего объёма задач запас огромный.
- **Лимиты подписки.** При упоре в лимит джоб просто упадёт с ошибкой — это
  нормально, следующий запуск швеи повторит. Ничего настраивать не нужно.
- **Качество = качество постановки.** Критерии приёмки в тексте задачи
  окупаются сильнее любого тюнинга промпта — используй шаблон
  «Agent task» (`.github/ISSUE_TEMPLATE/agent-task.md`).
- **Не давай авто-merge.** Просмотр PR — единственное место, где участие
  человека реально нужно.

---

## Autobot v2 — полностью автономный пайплайн (issue #36)

Autobot v2 расширяет автоматику до полного цикла: кодер открывает PR, ревью кода,
исправления, ревью продукта, исправления документации, merge — всё без участия оператора.
Человек нужен только в исключительных ситуациях (метка `needs-human`).

### Машина состояний (метки на PR)

```
[issue: claude-ready]
        │
        ▼ (claude-issue / claude-sweeper)
[PR: needs-code-review]
        │
        ▼ (claude-pr-review)
        ├─ CHANGES_REQUESTED → [PR: code-changes-requested]
        │                              │
        │               (claude-pr-fix, до 5 раундов)
        │                              │
        │                              └──────────────────┐
        │                                                  │
        └─ APPROVED → [PR: code-approved]                 │
                              │                            │
                              ▼ (claude-pr-product-review) │
                              ├─ user_guide.md не менялся  │
                              │   → [PR: product-approved] │
                              │                            │
                              ├─ CHANGES_REQUESTED         │
                              │   → [PR: product-changes-requested]
                              │           │
                              │   (claude-pr-product-fix, до 5 раундов)
                              │           │
                              │           └── → [PR: needs-code-review] ──┘
                              │
                              └─ APPROVED → [PR: product-approved]
                                                    │
                                                    ▼ (claude-pr-merge)
                                              squash merge + close issue
```

### 7 воркфлоу

| Файл | Триггер | Что делает |
|---|---|---|
| `claude-issue.yml` | issue labeled `claude-ready` | Агент-кодер решает задачу, открывает PR; tail ставит `needs-code-review`, снимает `claude-ready` |
| `claude-sweeper.yml` | schedule 6ч / workflow_dispatch | Подбирает накопившиеся `claude-ready`-issues и застрявшие; то же tail |
| `claude-pr-review.yml` | PR labeled `needs-code-review` | Агент-ревьюер читает diff, постит ревью + hidden-маркер вердикта; bash ставит `code-approved` или `code-changes-requested` |
| `claude-pr-fix.yml` | PR labeled `code-changes-requested` | Счётчик раундов (F2); агент-кодер исправляет; bash ставит `needs-code-review` |
| `claude-pr-product-review.yml` | PR labeled `code-approved` | Если `docs/user_guide.md` не менялся — `product-approved` сразу; иначе агент product-manager + вердикт |
| `claude-pr-product-fix.yml` | PR labeled `product-changes-requested` | Счётчик раундов (F2); агент-кодер правит docs; bash ставит `needs-code-review` |
| `claude-pr-merge.yml` | PR labeled `product-approved` | Только bash: ждёт CI, проверяет lint+test, squash-merge, закрывает issue через `closingIssuesReferences` |

### Два независимых счётчика раундов (F2)

Счётчики считают hidden-маркерные комментарии (append-only), а не правки тела PR.

| Счётчик | Маркер в комментарии | Ограничение |
|---|---|---|
| Раунды code-fix | `<!-- autobot:code-fix-round -->` | 5 раундов → `needs-human` |
| Раунды product-fix | `<!-- autobot:product-fix-round -->` | 5 раундов → `needs-human` |

При достижении лимита воркфлоу постит комментарий `[AUTOBOT]`, ставит метку `needs-human`
и останавливается. Ни один маршрут не продолжается автоматически после `needs-human`.

### Merge gate (F3)

`claude-pr-merge.yml` требует, чтобы check runs **`lint` и `test`** завершились со статусом
`success`. Статусы `skipped` и `neutral` не блокируют (джоб `build-push` пропускается на
PRах). Воркфлоу опрашивает GitHub API каждые 10 секунд, таймаут 20 минут. При красных
чеках или таймауте — комментарий `[AUTOBOT ERROR]` + `needs-human` + `exit 1`.

### Где живёт AUTOMATION_TOKEN (F1)

Секрет `AUTOMATION_TOKEN` — fine-grained PAT с правами на содержимое и метки репозитория.
Создаётся оператором один раз: Settings → Secrets and variables → Actions → `AUTOMATION_TOKEN`.
Все операции с метками (`gh pr edit --add-label / --remove-label`) используют этот PAT через
`GH_TOKEN: ${{ secrets.AUTOMATION_TOKEN }}`, чтобы label-change re-trigger отработал корректно.

Секрет `CLAUDE_CODE_OAUTH_TOKEN` используется только для аутентификации `claude-code-action`.
Агентские задания не делают операций с метками напрямую — это делает post-agent bash с PAT.

### Post-agent bash verification (cross-cutting)

Каждый джоб с агентом имеет шаг verification после `claude-code-action`. Причина:
`conclusion: success` в `claude-code-action` не означает, что агент успешно выполнил задачу —
`is_error` не проксируется. Verification проверяет реальный артефакт (PR создан, маркер-комментарий
присутствует). При неудаче: комментарий `[AUTOBOT ERROR]` + `needs-human` + `exit 1`.

### Процедура dry-run (оператор, после merge, F6)

**Важно:** label-triggered воркфлоу срабатывают только с default branch (main). Не запускай
dry-run до merge Autobot v2 в main.

1. Создай throwaway-issue с простым no-op заданием (например, «добавить комментарий в README»).
2. Поставь метку `claude-ready` на issue.
3. Следи за прогрессом: Actions → каждый воркфлоу должен отработать по цепочке.
4. Проверь финальный merge и закрытие issue.
5. Только после успешного dry-run запускай реальный #28.

### Метки (все 8 меток уже созданы)

| Метка | Смысл |
|---|---|
| `claude-ready` | Opt-in оператора |
| `claude-in-progress` | Замок очереди (кодер работает) |
| `needs-code-review` | PR готов к code review |
| `code-changes-requested` | Ревьюер запросил правки |
| `code-approved` | Code review пройден |
| `needs-product-review` | (зарезервировано, не используется в v2) |
| `product-changes-requested` | Product-manager запросил правки docs |
| `product-approved` | Product review пройден → merge |
| `needs-human` | Автоматика остановилась, нужен оператор |

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
