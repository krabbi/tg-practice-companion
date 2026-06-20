# Операционный гайд

## PM-triage — подготовка задачи (product-manager агент)

PM-triage превращает сырой или наспех сформулированный issue в корректно оформленный,
прежде чем он попадёт в очередь реализации. Это **предварительный этап** перед
`claude-queued` / `claude-ready`.

### Как запустить

Добавь метку `claude-triage` на любой issue. Воркфлоу `claude-pm-triage.yml` сработает
мгновенно; агент-product-manager прочитает тело issue и выполнит необходимые действия.

### Что делает агент

Агент классифицирует issue по одному из четырёх вариантов:

| Тип | Признак | Действие |
|---|---|---|
| **empty** | Тело пустое или не содержит намерения | Просит оператора описать задачу; тело не правит |
| **well-formed** | Есть заголовок + описание + хотя бы несколько критериев приёмки | Постит подтверждение; тело не правит |
| **small** | Одно связное изменение в одном слое архитектуры | Редактирует тело issue: заголовок + описание + AC по стандартному шаблону; постит комментарий с объяснением изменений |
| **large** | Несколько независимых шагов или несколько слоёв архитектуры | Создаёт дочерние issues с маркерами `Blocked by #N` (точный формат, требуемый chain-driver'ом); обновляет тело родительского issue чеклистом подзадач; постит комментарий со структурой декомпозиции |

После классификации и действия агент всегда:
1. Снимает метку `claude-triage`.
2. Добавляет метку `needs-human`.
3. Постит комментарий: «Triage done — review and queue manually».

### Шаг оператора после triage

1. Прочитай результат (обновлённое тело issue и комментарий агента).
2. Если результат устраивает — сними `needs-human`, добавь `claude-queued` (или `claude-ready`
   для задач без зависимостей). Цепочный драйвер и кодер подхватят дальше.
3. Если не устраивает — сними `needs-human`, внеси правки вручную, затем при необходимости
   снова добавь `claude-triage` (повторный тriage).

### Эвристика small vs large

- **small** — одно изменение в одном слое (handler, service, repository, model, config,
  workflow, docs). Как правило, умещается в один PR.
- **large** — несколько независимых изменений, несколько слоёв, или задача, которую
  разумно закрыть несколькими последовательными PR. Требует декомпозиции.

### Повторный triage

Если оператора не устроил результат: сними `needs-human`, подчисти частично созданные
дочерние issues (если были), затем добавь `claude-triage` снова.

### Пауза при исчерпании лимита подписки

При ошибке агента (`is_error: true`, `subtype != error_max_turns`) issue помечается
`autobot-paused`; счётчик `<!-- autobot:triage-pause-count -->` ведётся в комментариях.
После **5 пауз подряд** ставится `needs-human` вместо `autobot-paused`.
Для возобновления вручную добавь `claude-triage` снова (после сброса лимита).

### Создание метки (один раз, идемпотентно)

```bash
gh label create "claude-triage" \
  --color "E4E669" \
  --description "Raw issue awaiting PM-triage by product-manager agent"
```

---

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
- **Лимиты подписки.** При упоре в 5-часовой лимит агент возвращается с `is_error`
  не сделав работы. На issue-стадии это даёт `needs-human` (следующий запуск швеи
  повторит); на PR-стадиях — автоматическую паузу `autobot-paused` с возобновлением
  кроном `claude-pr-resume` (см. Autobot v2 → «Пауза на лимите подписки»).
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
                                                    ▼ (claude-pr-merge: CI gate lint+test)
                                              ├─ CI failure → [PR: code-changes-requested] ──┐
                                              │     (назад в петлю code-fix, cap = 5)         │
                                              │                                              ─┘
                                              └─ CI green → squash merge + close issue
```

### 8 воркфлоу

| Файл | Триггер | Что делает |
|---|---|---|
| `claude-issue.yml` | issue labeled `claude-ready` | Агент-кодер решает задачу, открывает PR; tail ставит `needs-code-review`, снимает `claude-ready` |
| `claude-sweeper.yml` | schedule 6ч / workflow_dispatch | Подбирает накопившиеся `claude-ready`-issues и застрявшие; то же tail |
| `claude-pr-review.yml` | PR labeled `needs-code-review` | Агент-ревьюер читает diff, постит ревью + hidden-маркер вердикта; bash ставит `code-approved` или `code-changes-requested` |
| `claude-pr-fix.yml` | PR labeled `code-changes-requested` | Счётчик раундов (F2); агент-кодер исправляет; bash ставит `needs-code-review` |
| `claude-pr-product-review.yml` | PR labeled `code-approved` | Если `docs/user_guide.md` не менялся — `product-approved` сразу; иначе агент product-manager + вердикт |
| `claude-pr-product-fix.yml` | PR labeled `product-changes-requested` | Счётчик раундов (F2); агент-кодер правит docs; bash ставит `needs-code-review` |
| `claude-pr-merge.yml` | PR labeled `product-approved` | Только bash: ждёт CI, проверяет lint+test; зелёный — squash-merge + закрытие issue через `closingIssuesReferences`; реальное падение CI — назад в петлю code-fix (`code-changes-requested`); отсутствие/нечитаемость чека — `needs-human` |
| `claude-pr-resume.yml` | schedule ~5ч / workflow_dispatch | Только bash: находит PR с `autobot-paused`, снимает все стадийные метки и перезапускает флоу с `needs-code-review` (см. «Пауза на лимите подписки») |

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
`success` (плюс `frontend`, если присутствует). Статусы `skipped` и `neutral` не блокируют
(джоб `build-push` пропускается на PRах). Воркфлоу опрашивает GitHub API каждые 10 секунд,
таймаут 20 минут.

Поведение при провале **различается по причине**:

- **Реальное падение чека** (`lint`/`test`/`frontend` = `failure`) — это дефект кода, который
  кодер может исправить. Gate постит комментарий `[AUTOBOT CI FAILURE]` с указанием упавших
  чеков и **возвращает PR в петлю code-fix**: снимает устаревшие `code-approved` /
  `product-approved`, ставит `code-changes-requested` (триггерит только `claude-pr-fix`).
  Тот же счётчик `<!-- autobot:code-fix-round -->` (cap = 5) ограничивает число попыток: если
  CI-падение агент починить не может, после 5 раундов петля сама выходит в `needs-human` —
  бесконечного пинг-понга нет. `claude-pr-fix` распознаёт `[AUTOBOT CI FAILURE]`, читает
  логи упавшего рана (`gh run view --log-failed`) и чинит причину, а не только ревью-замечания.
- **Чек отсутствует / нечитаем** (`lint` или `test` не найдены, либо API-ошибка чтения) или
  **таймаут ожидания** — это инфра/конфиг-аномалия, которую агент починить не может:
  комментарий `[AUTOBOT ERROR]` + `needs-human` + `exit 1` (прежнее поведение).

> Историческая дыра (PR #118, 2026-06-18): merge gate валил в `needs-human` любое падение CI,
> хотя `test` упал на Postgres-only баге миграции (`recreate="always"` в `batch_alter_table` →
> `DependentObjectsStillExistError`), а ревьюер прогонял тесты на sqlite и не увидел этого.
> Маршрута «CI-провал → автофикс» не было — теперь есть.

### Пауза на лимите подписки (F7)

Если 5-часовой лимит Pro-подписки исчерпан, `claude-code-action` возвращается за
~0.4 сек с `is_error: true` и `num_turns: 1` (на cap-хите `subtype` врёт «success»),
но GitHub-исход джоба — `success` (экшен глотает `is_error`). Без защиты это:
- старые версии флипали метку и крутили петлю review↔fix (реальный кейс PR #57
  2026-06-15: ~37 кругов, 75 вырожденных прогонов за 47 минут, пока лимит не сбросился);
- текущие версии валят PR в `needs-human` на пустом месте.

**Защита.** Каждая PR-стадия после агента имеет шаг `Pause on subscription-limit
exhaustion`: читает `execution_file` (output `claude-code-action`), и если
`is_error == true && subtype != "error_max_turns"` — НЕ флипает метку, а вешает
`autobot-paused` и останавливается. Ключуемся от `is_error`, не от `subtype`
(на cap-хите он лживо «success»). `error_max_turns` — настоящий «не уложился», идёт
по обычному пути `needs-human`. Это ловит и мгновенный cap (`num_turns:1`), и обрыв
в середине ревью (`num_turns>1`, `subtype` `error_during_execution`).

**Возобновление.** `claude-pr-resume.yml` (крон ~5ч + `workflow_dispatch`) находит PR
с `autobot-paused`, снимает его и все стадийные метки и ставит `needs-code-review` —
флоу стартует с начала. Фазу паузы не восстанавливаем (cap может ударить в середине,
точно её не определить), а пайплайн идемпотентен: ревьюер судит по текущему диффу.
В промпты ревью добавлено явное «PR мог быть перезапущен — оценивай текущее состояние».

**Предохранитель от вечной паузы.** Каждая пауза постит маркер `<!-- autobot:pause-count -->`.
На 3-й паузе подряд (≥ ~15ч — значит это не транзиентный лимит, а реальная ошибка)
стадия ставит `needs-human` вместо `autobot-paused`.

### Защита форматирования (ruff format)

Чтобы неотформатированный код не доходил до CI (исторический кейс PR #58: `ruff format
--check` падал → merge gate ставил `needs-human`), форматирование закреплено в три слоя:

1. **pre-commit хук у агента.** `claude-issue.yml` и `claude-sweeper.yml` перед запуском
   `claude-code-action` ставят `pre-commit install` в раннере, поэтому `git commit` агента
   автоматически прогоняет `ruff` + `ruff-format`. Конфиг — `.pre-commit-config.yaml`.
2. **Детерминированный backstop.** Шаг `Enforce formatting on PR branch` после агента
   переформатирует запушенную ветку и, только если что-то изменилось, коммитит и пушит фикс
   **через `AUTOMATION_TOKEN`** (push дефолтным `GITHUB_TOKEN` не перезапустил бы CI). Скоуп —
   только `ruff format`; настоящие ошибки `ruff check` остаются на CI + merge gate.
3. **Merge gate** (ниже) — финальный предохранитель.

Версия ruff закреплена идентично в `.pre-commit-config.yaml`, `.github/workflows/ci.yml` и
`pyproject.toml` (`ruff==0.15.17`) — рассинхрон версий снова открыл бы дыру «прошло хук, упало
на CI». При апдейте ruff бампать все три точки одновременно.

Локально хук ставится автоматически через `make install` (`pre-commit install`).

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
`is_error` не проксируется. Verification проверяет реальный артефакт (PR создан, маркер-вердикт
присутствует). При неудаче: комментарий `[AUTOBOT ERROR]` + `needs-human` + `exit 1`.

**Каналы поиска вердикта.** Агент может опубликовать вердикт двумя способами — через
`gh pr comment` (issue comment) или через `gh pr review` (PR review). Парсер вердикта
в `claude-pr-review.yml` и `claude-pr-product-review.yml` собирает текст из **обоих каналов**
перед grep-ом:

```bash
COMMENTS=$(gh pr view "$PR_NUMBER" --json comments --jq '.comments[].body')
REVIEWS=$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews" --jq '.[].body')
HAYSTACK="${COMMENTS}"$'\n'"${REVIEWS}"
```

`gh pr view --json comments` возвращает только issue-комментарии; тела PR-ревью (endpoint
`pulls/{n}/reviews`) туда не попадают. Без объединения каналов вердикт, опубликованный
через `gh pr review`, не обнаруживается, PR ошибочно попадает в `needs-human`.

### Процедура dry-run (оператор, после merge, F6)

**Важно:** label-triggered воркфлоу срабатывают только с default branch (main). Не запускай
dry-run до merge Autobot v2 в main.

1. Создай throwaway-issue с простым no-op заданием (например, «добавить комментарий в README»).
2. Поставь метку `claude-ready` на issue.
3. Следи за прогрессом: Actions → каждый воркфлоу должен отработать по цепочке.
4. Проверь финальный merge и закрытие issue.
5. Только после успешного dry-run запускай реальный #28.

### Метки (уже созданы в репозитории)

| Метка | Смысл |
|---|---|
| `claude-triage` | Opt-in: issue ожидает PM-triage агентом product-manager |
| `claude-ready` | Opt-in оператора; задача готова к немедленному подхвату кодером |
| `claude-queued` | Задача в цепочке — ждёт, пока закроются все блокирующие issues; драйвер сам переведёт в `claude-ready` |
| `claude-in-progress` | Замок очереди (кодер работает) |
| `needs-code-review` | PR готов к code review |
| `code-changes-requested` | Ревьюер запросил правки |
| `code-approved` | Code review пройден |
| `needs-product-review` | (зарезервировано, не используется в v2) |
| `product-changes-requested` | Product-manager запросил правки docs |
| `product-approved` | Product review пройден → merge |
| `autobot-paused` | Issue или PR на паузе из-за лимита подписки; `claude-pr-resume` перезапустит флоу |
| `needs-human` | Автоматика остановилась, нужен оператор |

> **Создание меток в репозитории:**
> ```bash
> gh label create "claude-queued" --color "BFD4F2" --description "Enrolled in an autobot chain — waiting for blockers to close"
> ```
> Метки `claude-ready`, `claude-in-progress`, `autobot-paused`, `needs-human` и стадийные метки PR уже созданы ранее.

---

## Autobot chain driver (issue #80)

Цепочка задач — группа issues, связанных зависимостями «сначала #N, потом меня».
Драйвер (`claude-chain-driver.yml`) управляет очередью автоматически: смотрит,
какие блокирующие issues уже закрыты, и переводит следующую задачу из
`claude-queued` → `claude-ready` ровно тогда, когда конвейер освободился.

### Как объявить цепочку

1. Создай каждую задачу как обычный issue.
2. В тело каждой зависимой задачи добавь строку (одну или несколько):
   ```
   Blocked by #N
   ```
   Формат регистронезависимый; поддерживается несколько строк / несколько номеров на строке:
   ```
   Blocked by #42
   Blocked by #43
   Blocked by #42, #43
   ```

   > ⚠️ **Точный формат обязателен.** Драйвер ищет маркер регулярным выражением
   > `blocked by #[0-9]+` — между `by` и `#` должен стоять **ровно один пробел**.
   > Любая markdown-стилизация ломает распознавание, и задача будет ошибочно
   > считаться задачей **без блокеров** (сразу eligible). Так **нельзя**:
   > `**Blocked by:** #42` — двоеточие и `**` разрывают `by #`.
   >
   > Кроме того, строка с маркером должна содержать **только** номера блокеров.
   > Не пиши блокеры на одной строке с другими `#`-ссылками (например `epic #65`
   > или `Blocks: #99`) — драйвер захватит **все** `#N` со строки и посчитает их
   > блокерами. Выноси `Blocked by #N` на отдельную строку.
3. Проставь метку `claude-queued` на все задачи цепочки.
   **Не** ставь `claude-ready` вручную — это сделает драйвер.
4. Если хочешь, чтобы какая-то задача ушла в работу первой (стартовая),
   можешь поставить на неё `claude-ready` напрямую (без `claude-queued`).

Пример цепочки из трёх задач:

```
#10 — базовая схема   → claude-queued, нет блокеров
#11 — сервис          → claude-queued, Blocked by #10
#12 — хэндлер         → claude-queued, Blocked by #11
```

Когда #10 смержится (issue закроется), драйвер переведёт #11 в `claude-ready`.
Когда #11 смержится — переведёт #12.

### Машина состояний (метки на issue)

```
[оператор ставит claude-queued]
        │
        │  (claude-chain-driver: все блокеры закрыты и конвейер свободен)
        ▼
[claude-ready]
        │
        │  (claude-issue / claude-sweeper)
        ▼
[claude-in-progress] → ... → PR merge → issue CLOSED
```

### Воркфлоу `claude-chain-driver.yml`

| Параметр | Значение |
|---|---|
| Триггер | `issues: [closed]` (мгновенно) + `schedule: 0 */6 * * *` (раз в 6 часов) |
| Исполнение | Чистый bash, никакого агента |
| Токен | `AUTOMATION_TOKEN` (PAT) — нужен для каскада label-событий |
| Таймаут | 10 минут |

**Алгоритм:**

1. **Guard** — ничего не делать, если конвейер занят:
   - есть issue с `claude-ready` или `claude-in-progress`, **или**
   - есть открытый PR с любой стадийной меткой (кроме `autobot-paused` / `needs-human`).
2. **Поиск** — из всех `claude-queued` issues выбрать те, у которых все
   `Blocked by #N` закрыты. Tie-break: **наименьший номер issue**.
3. **Продвижение** — снять `claude-queued`, поставить `claude-ready`
   (одно issue за раз). Label-add запускает `claude-issue.yml`.

### Пауза на лимите подписки (coder stage)

Расширение механизма PR #61 на стадию кодера:

- После шага `claude-code-action` в `claude-issue.yml` и `claude-sweeper.yml`
  читается `execution_file`. Если `is_error == true && subtype != "error_max_turns"` —
  issue паркуется как `autobot-paused` (снимаются `claude-in-progress` и `claude-ready`).
- `claude-pr-resume.yml` (крон ~5ч + `workflow_dispatch`) находит `autobot-paused` issues
  и снимает паузу: убирает `autobot-paused`, возвращает `claude-ready` — кодер запустится
  снова.
- **Предохранитель:** счётчик `<!-- autobot:issue-pause-count -->` в комментариях issue.
  После **5 пауз подряд** ставится `needs-human` вместо `autobot-paused`.
- `error_max_turns` — настоящий «агент не уложился в лимит ходов» → `needs-human`
  по обычному пути (не пауза).

### DAG-зависимости

Помимо линейных цепочек, поддерживается произвольный ориентированный граф (DAG):
issue может иметь несколько блокеров. Он перейдёт в `claude-ready` только когда
**все** его `Blocked by #N` будут закрыты.

```
#10 ──┐
      ├──▶ #12 (Blocked by #10, Blocked by #11)
#11 ──┘
```

Циклические зависимости не обнаруживаются автоматически (драйвер просто не найдёт
eligible issue и остановится). Не создавай циклических зависимостей.

### Dry-run (после merge в main)

Label-triggered воркфлоу срабатывают только с HEAD main. Для теста цепочки:

1. Создай два throwaway-issues: #A (без блокеров) и #B (`Blocked by #A`).
2. Поставь `claude-queued` на оба.
3. Проверь, что `claude-chain-driver` (Actions → Claude chain driver) при закрытии
   #A переводит #B в `claude-ready` и кодер начинает работу.
4. Убедись, что guard не продвигает #B, пока конвейер занят.
5. **Регрессия многострочного тела (важно).** Создай throwaway-issue #C с
   многострочным телом, где `Blocked by #N` стоит **не на первой строке**, а
   ниже по тексту, например:

   ```
   Контекст задачи.
   Ещё одна строка описания.

   Blocked by #A
   Заключительная строка.
   ```

   Поставь `claude-queued`. Закрой #A и убедись, что драйвер всё равно нашёл
   зависимость `#A` и продвинул #C только после её закрытия (а не сразу при
   постановке метки). Это страхует от регрессии, когда тело сериализовалось
   с буквальными переносами строк и блокер на не-первой строке терялся.

### Пауза на лимите подписки (таблица маркеров)

| Маркер | Место | Назначение |
|---|---|---|
| `<!-- autobot:issue-pause-count -->` | комментарий на issue | Счётчик пауз кодера; ≥ 5 → `needs-human` |
| `<!-- autobot:pause-count -->` | комментарий на PR | Счётчик пауз PR-стадий; ≥ 3 → `needs-human` |
| `<!-- autobot:code-fix-round -->` | комментарий на PR | Счётчик раундов code-fix; ≥ 5 → `needs-human` |
| `<!-- autobot:product-fix-round -->` | комментарий на PR | Счётчик раундов product-fix; ≥ 5 → `needs-human` |

---

## Web admin entry points (AC-19)

### `/admin` command

The bot exposes a `/admin` command that replies with an inline Web App button opening
the admin TMA directly inside Telegram.  It requires `WEB_APP_URL` to be set in the
bot's environment; when the variable is empty the bot replies with a localised
"not configured" message instead.

### BotFather persistent Menu Button (alternative launch surface)

As an alternative (or complement) to the `/admin` command, BotFather lets you pin a
persistent **Menu Button** that always opens the Mini App — visible at the bottom left of
the chat input bar.  To configure it:

1. Open `@BotFather` in Telegram and send `/mybots`.
2. Select your bot → **Bot Settings** → **Menu Button**.
3. Choose **Edit menu button URL** and paste the HTTPS URL of the deployed SPA (same
   value as `WEB_APP_URL`).
4. The button label defaults to "Menu" — change it with **Edit menu button text** if
   desired.

The persistent button provides `initData` just like the `/admin` inline button, so TMA
authentication works identically.

---

## Backblaze B2 media storage setup

Media files (audio practices, motivational images) uploaded through the web admin are stored
in an S3-compatible Backblaze B2 bucket. The bot service does **not** need these credentials —
only the `web` Docker Compose service uses them.

### 1. Create a B2 bucket

1. Sign in to [backblaze.com](https://www.backblaze.com) → **B2 Cloud Storage** → **Buckets**.
2. Click **Create a Bucket**:
   - **Bucket name**: choose a globally unique name (e.g. `my-practice-media`).
   - **Files in bucket are**: **Private** (objects are never publicly accessible; access is via presigned URLs).
   - Leave all other settings at their defaults.
3. Note the **Endpoint** shown on the bucket detail page — it looks like
   `s3.us-west-004.backblazeb2.com`.  The region is the part after `s3.` and before
   `.backblazeb2.com` (e.g. `us-west-004`).

### 2. Create an application key (scoped to the bucket)

**Do not use the master application key.** Create a dedicated key scoped only to this bucket:

1. Go to **Account** → **Application Keys** → **Add a New Application Key**.
2. **Name of Key**: e.g. `practice-web`.
3. **Allow access to Bucket(s)**: select the bucket you just created.
4. **Type of Access**: **Read and Write**.
5. Leave **File name prefix** and **Duration** empty (no expiry).
6. Click **Create New Key** and **immediately copy both values**:
   - **keyID** → this is `S3_ACCESS_KEY_ID`
   - **applicationKey** → this is `S3_SECRET_ACCESS_KEY` (shown only once)

### 3. Find the S3 endpoint and region

From the bucket detail page:
- **Endpoint**: `https://s3.<region>.backblazeb2.com` — copy the full HTTPS URL.
- **Region**: the `<region>` portion, e.g. `us-west-004`.

### 4. Set the required environment variables

Add the following to `.env` (web service only; the bot service ignores them):

```bash
S3_ENDPOINT_URL=https://s3.us-west-004.backblazeb2.com   # full HTTPS URL from step 3
S3_REGION=us-west-004                                     # region from step 3
S3_BUCKET=my-practice-media                               # bucket name from step 1
S3_ACCESS_KEY_ID=your-application-key-id                  # keyID from step 2
S3_SECRET_ACCESS_KEY=your-application-key                 # applicationKey from step 2
S3_PRESIGN_EXPIRY_SECONDS=900                             # optional; default 900 (15 min)
MEDIA_MAX_IMAGE_BYTES=10485760                            # optional; default 10 MB
MEDIA_MAX_AUDIO_BYTES=52428800                            # optional; default 50 MB (Telegram cap)
```

### 5. Notes

- **SigV4 only.** Backblaze B2 accepts only AWS Signature Version 4 — boto3 (used by the
  service) sends SigV4 by default, so no special configuration is needed.
- **Per-kind upload limits** are enforced at the API layer (`MEDIA_MAX_IMAGE_BYTES`, default
  10 MB; `MEDIA_MAX_AUDIO_BYTES`, default 50 MB); nginx's `client_max_body_size` is driven by
  the audio cap. The audio cap matches Telegram's 50 MB bot-send limit so every uploaded audio
  is deliverable by the bot — raising it past 50 MB would let uploads succeed but break delivery
  unless a self-hosted Bot API server is used. B2 itself has a 5 GB object limit, so the
  application limits are the binding constraint. The size check runs **before** the S3 upload,
  so an oversized file is rejected with a clean 413 and never leaves an orphan object.
- **Portability to AWS S3.** Swap `S3_ENDPOINT_URL` (remove it or set it to
  `https://s3.amazonaws.com`), `S3_REGION` (e.g. `us-east-1`), `S3_BUCKET`, and the key
  pair.  No code changes required.
- **No local media volume.** There is no `practice_media` Docker volume or
  `MEDIA_STORAGE_DIR` in this deployment. All media objects live in B2.

---

## Web admin deploy (Stage 2, AC-19)

The web admin runs as two Docker Compose services under the `web` profile:

| Service | Role |
|---|---|
| `web` | FastAPI/uvicorn — business logic and REST API on internal port `WEB_PORT` (default 8000) |
| `nginx` | Serves the built Vue SPA and proxies `/api/*` → `web:8000`; exposed on `NGINX_PORT` (default 4100) |

The host-level reverse proxy (e.g. Caddy or nginx on the host) maps the admin domain →
`127.0.0.1:4100` and handles TLS.  TMA requires a public HTTPS URL — the host proxy provides it.

### First-time web admin deploy

**Prerequisites:** Docker + Docker Compose v2, Node 20 (to build the SPA), the bot already
running (`--profile bot`), `.env` with all required secrets.

```bash
# 1. Generate JWT_SECRET (keep it secret — never commit to git)
openssl rand -hex 32

# 2. Edit .env — fill in the web admin variables:
#   JWT_SECRET=<generated above>
#   CORS_ORIGINS=https://admin.yourdomain.example.com
#   NGINX_PORT=4100
#   WEB_APP_URL=https://admin.yourdomain.example.com
#   S3_ENDPOINT_URL, S3_REGION, S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
#   (see "Backblaze B2 media storage setup" section above for details)

# 3. Build the Vue SPA (produces frontend/dist/)
cd frontend && npm ci && npm run build && cd ..

# 4. Map the admin domain on the host reverse proxy to 127.0.0.1:4100
#    (see your host proxy documentation — Caddy example below)

# 5. Start web profile (nginx + web + db)
docker compose --profile web up -d

# 6. Check logs
docker compose logs web --tail 30
docker compose logs nginx --tail 30
```

**Caddy example** (add to `/etc/caddy/Caddyfile` on the host):

```caddyfile
admin.yourdomain.example.com {
    reverse_proxy 127.0.0.1:4100
}
```

After Caddy reloads, the SPA is available at `https://admin.yourdomain.example.com`.

### Register the admin as a Telegram Mini App

Once the HTTPS URL is live, register it with BotFather so the `/admin` command and Menu
Button work:

1. Open `@BotFather` → `/mybots` → select your bot → **Bot Settings** → **Menu Button**.
2. Set **Edit menu button URL** to the HTTPS admin URL (same as `WEB_APP_URL`).
3. Set `WEB_APP_URL` in `.env` to the same HTTPS URL and restart the bot:

```bash
docker compose --profile bot restart bot
```

The `/admin` command now opens the Mini App directly inside Telegram.

### Updating the SPA after a frontend change

```bash
cd frontend && npm run build && cd ..
docker compose --profile web restart nginx
```

The new `frontend/dist/` files are picked up on nginx restart (bind-mounted from the host).

### Environment variable reference — web profile

| Variable | Required | Default | Notes |
|---|---|---|---|
| `JWT_SECRET` | yes | — | Random hex string; generate with `openssl rand -hex 32` |
| `CORS_ORIGINS` | no | `""` | Comma-separated HTTPS origins allowed by the API |
| `WEB_PORT` | no | `8000` | Internal uvicorn port (used only inside Docker network) |
| `NGINX_PORT` | no | `4100` | Host port nginx listens on; host proxy maps domain → this |
| `WEB_APP_URL` | no | `""` | HTTPS URL of the deployed SPA; required for `/admin` TMA button |
| `S3_ENDPOINT_URL` | yes | — | Full HTTPS endpoint, e.g. `https://s3.us-west-004.backblazeb2.com` |
| `S3_REGION` | yes | — | S3 region name, e.g. `us-west-004` |
| `S3_BUCKET` | yes | — | S3 bucket name |
| `S3_ACCESS_KEY_ID` | yes | — | S3 / B2 application key ID |
| `S3_SECRET_ACCESS_KEY` | yes | — | S3 / B2 application key secret |
| `S3_PRESIGN_EXPIRY_SECONDS` | no | `900` | Presigned URL TTL in seconds (15 min) |
| `MEDIA_MAX_IMAGE_BYTES` | no | `10485760` | Maximum image upload size (10 MB) |
| `MEDIA_MAX_AUDIO_BYTES` | no | `52428800` | Maximum audio upload size (50 MB — Telegram bot-send cap); also drives nginx `client_max_body_size` |

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

Use `python -m cli.seed practices content/practices.yaml --user-id <TELEGRAM_USER_ID>` to load
or update practice rows for a specific user.
The seed is idempotent (upserts by `(user_id, name)`). See `content/practices.example.yaml` for the
full YAML schema and the reference daily cycle.

---

## 06:00 morning block — structure and 06:00 collision (M3.4)

### Morning block delivery order

At 06:00 local time the scheduler fires in this sequence:

| Step | What | Mechanism |
|---|---|---|
| 1 | Morning blessing (rotating) | Inline in tick, from `morning_blessings` table |
| 2 | AI analysis dispatch | Off-tick job `run_morning_analysis` added to scheduler |
| 3 | Morning practice (sort_order ≤ 30) | Practice delivery loop (`compose()` order) |
| 4 | Motivational image (sort_order ≤ 40) | Practice delivery loop |
| 5 | Hourly thought question (sort_order ≥ 100) | Practice delivery loop — 06:00 collision, see below |

The AI analysis text arrives whenever the LLM responds (could be seconds to minutes after
dispatch).  From the user's perspective: blessing → analysis text → morning practice → image.

### Blessing rotation

Morning blessings are stored in the `morning_blessings` table (each row has a unique
`rotation_order`).  The scheduler selects today's blessing using a date-derived index:

```
idx = today.toordinal() % count_of_active_blessings
```

Consecutive calendar days advance through the list in `rotation_order` sequence and
wrap back to the first blessing after the last one.  The rotation requires no mutable
cursor state — it is fully determined by the calendar date (AC-3).

Deduplication: `users.last_blessing_date` tracks the last day a blessing was sent.
A second tick at the same 06:00 slot (e.g., after a bot restart) does not resend.

Seed blessings via `python -m cli.seed blessings content/blessings.yaml --user-id <TELEGRAM_USER_ID>`.

### 06:00 hourly-question collision

The hourly thought-registration question configured with `interval_hours=1,
anchor_hour=0` fires at every whole hour anchored to local midnight — including 06:00.
This collision with the morning block is **intentional and expected**:

- The question's `sort_order` (≥ 100 by convention) places it **after** the morning block
  items (sort_order ≤ 40), so `compose()` delivers it last.
- From the user's perspective it arrives as a natural follow-up to the morning motivation.

**To shift the first hourly question to 07:00** (leaving the morning block undisturbed):
set `anchor_hour=7` on the hourly question practice row.  This is a data-only change
(no code modification required, AC-4):

```yaml
- name: Hourly thought-registration question
  ...
  interval_hours: 1
  anchor_hour: 7   # ← changed from 0; first slot is now 07:00
  anchor_minute: 0
```

After re-seeding with `python -m cli.seed practices content/practices.yaml --user-id <TELEGRAM_USER_ID>` the new
cadence takes effect on the next tick — no restart needed.

---

## Automatic CD — deploy on merge to main (issue #149)

Every merge to `main` triggers an automatic deploy via GitHub Actions once the
`build-push` job (which publishes the fresh bot image to GHCR) succeeds.

### How it works

```
push to main
    │
    └─ ci.yml: lint + test
              └─ build-push  (publishes ghcr.io/krabbi/tg-practice-companion:latest)
                        │
                        └─ deploy.yml triggered by workflow_run on CI completion
                                  └─ SSH into server → bash scripts/deploy.sh
```

`deploy.yml` uses a `workflow_run` trigger keyed on the `CI` workflow and gates the job
on `github.event.workflow_run.conclusion == 'success'` — the deploy only fires when the
full CI pipeline (lint + test + build-push) succeeds on `main`.

`scripts/deploy.sh` performs the ordered redeploy:

1. `git fetch && git checkout main && git pull origin main` — update source
2. `docker compose pull bot` — pull the freshly published bot image
3. Build the Vue SPA in a throwaway `node:20-alpine` container (server has no Node);
   writes into `frontend/dist/`. **A build failure aborts the script immediately** —
   `docker compose up -d` is never reached with a stale or partial `dist/`.
4. `docker compose build web` — rebuild the web image from updated source
5. `docker compose --profile bot up -d bot` — (re)start the bot; the entrypoint
   automatically runs `alembic upgrade head` before the bot process starts
6. Wait (up to 120 s) for the bot container to become healthy — the `bot` service has a
   Docker `healthcheck` (`python -c "import sys; sys.exit(0)"`, `start_period: 60s`) so
   the wait loop polls `docker inspect` until status is `healthy`, guaranteeing migrations
   are committed before web starts (AC-3)
7. `docker compose --profile web up -d` — (re)start web + nginx with fresh dist/

### Required repository secrets

Set these in **Settings → Secrets and variables → Actions** (never commit to git):

| Secret | Value |
|---|---|
| `DEPLOY_SSH_KEY` | Private SSH key for the deploy user on the server; use a dedicated key scoped to a single deploy user with key-only auth |
| `DEPLOY_HOST` | Server hostname or IP |
| `DEPLOY_USER` | SSH username on the server (e.g. `deploy`) |
| `DEPLOY_PATH` | Absolute path to the repository checkout on the server (e.g. `/srv/tg-practice-companion`) |

The `AUTOMATION_TOKEN` and `CLAUDE_CODE_OAUTH_TOKEN` secrets used by the autobot
pipeline are separate — they are not needed for deployment.

### Re-running a failed deploy

A failed deploy shows as a red `deploy` job in Actions.  Click **Re-run failed jobs**
to retry (the script is idempotent — safe to re-run).  Alternatively, SSH into the
server and run the manual procedure below.

### Self-hosted runner (future alternative)

The current approach (GitHub-hosted runner + SSH push) requires inbound SSH from
GitHub's runner IP ranges and a deploy key secret.  A self-hosted runner on the
production box eliminates the inbound SSH requirement: replace `runs-on: ubuntu-latest`
with `runs-on: self-hosted` in `deploy.yml` and register the runner via
`Settings → Actions → Runners → New self-hosted runner`.  Out of scope for the
first iteration.

---

## Production deployment (M6, AC-15)

### First-time deploy

**Prerequisites:** Docker + Docker Compose v2, access to the server, `.env` file with all
required secrets.

```bash
# 1. Clone the repo and copy the env template
git clone https://github.com/krabbi/tg-practice-companion.git
cd tg-practice-companion
cp .env.example .env
# Edit .env: fill in TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, GROQ_API_KEY,
#   ALLOWED_USER_IDS, POSTGRES_PASSWORD (generate a random string)

# 2. Start database + bot
docker compose --profile bot up -d

# The entrypoint automatically runs `alembic upgrade head` before starting the bot.
# Check logs to confirm a clean start:
docker compose logs bot --tail 50
```

### Starting/stopping services

```bash
# Start bot + db
docker compose --profile bot up -d

# Stop everything
docker compose down

# Restart only the bot (e.g. after env change)
docker compose --profile bot restart bot
```

### Pulling a new image after a release

The bot image is published to `ghcr.io/krabbi/tg-practice-companion:latest` on every push
to `main`.  To deploy a new release:

```bash
docker compose pull bot
docker compose --profile bot up -d
```

Or run [Watchtower](https://containrrr.dev/watchtower/) to automatically poll and update:

```bash
docker compose --profile watchtower up -d
```

### Environment variable reference

| Variable | Required | Default | Notes |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | — | From @BotFather |
| `ANTHROPIC_API_KEY` | yes | — | AI analysis (AC-11, AC-16) |
| `GROQ_API_KEY` | no | `""` | Whisper voice transcription; disable by leaving empty |
| `ALLOWED_USER_IDS` | yes | — | Comma-separated Telegram user IDs |
| `POSTGRES_PASSWORD` | yes | — | PostgreSQL password; never commit to git |
| `POSTGRES_USER` | no | `practice` | PostgreSQL user |
| `MONTHLY_COST_LIMIT_USD` | no | `10.0` | Hard cost ceiling per month (AC-16) |
| `ANALYSIS_COST_CAP_USD` | no | `0.05` | Per-run ceiling for morning analysis (AC-11) |
| `SEND_WINDOW_START` | no | `6` | First hour (inclusive) of the send window |
| `SEND_WINDOW_END` | no | `22` | Last hour (exclusive) of the send window |
| `LLM_MODEL` | no | `claude-haiku-4-5-20251001` | AI model for analysis |
| `DEFAULT_LANGUAGE` | no | `ru` | Bot UI language |

No secrets are baked into the Docker image or `docker-compose.yml`.  All credentials are
injected at runtime via environment variables.

### Database backup

The Postgres data lives in the `practice_pgdata` Docker volume.  To back it up:

```bash
# Dump to a local file
docker compose exec db pg_dump -U practice practice > backup_$(date +%F).sql

# Restore from a dump
docker compose exec -T db psql -U practice practice < backup_YYYY-MM-DD.sql
```

Schedule this with cron on the host, e.g. daily at 03:00:

```cron
0 3 * * * cd /path/to/tg-practice-companion && docker compose exec -T db pg_dump -U practice practice > /backups/practice_$(date +\%F).sql
```

---

## Content loading (operator workflows)

### Workflow A — YAML + make seed (recommended)

Edit the YAML files in `content/`, then run (replace `<UID>` with the target user's Telegram ID):

```bash
# Locally (requires .env and DB running):
python -m cli.seed practices content/practices.yaml --user-id <UID>
python -m cli.seed blessings content/blessings.yaml --user-id <UID>

# Via Docker Compose (no local Python setup needed).
# The `-v` mount is required: the image bakes only the example YAML, so the host
# content/ directory (your edited files) must be mounted over /app/content.
docker compose run --rm -v "$PWD/content:/app/content" bot python -m cli.seed practices content/practices.yaml --user-id <UID>
docker compose run --rm -v "$PWD/content:/app/content" bot python -m cli.seed blessings content/blessings.yaml --user-id <UID>
```

All seed commands are **idempotent** — safe to re-run after any edit.

### Workflow B — direct SQL

For quick one-off changes without going through YAML:

```sql
-- Add a practice
INSERT INTO practices (id, name, content_type, content, periodicity_type,
                       schedule_times, anchor_hour, anchor_minute, active, sort_order)
VALUES (gen_random_uuid(), 'New reminder', 'text', 'Stay hydrated!',
        'fixed_times', '["10:00"]', 0, 0, true, 500);

-- Deactivate a practice
UPDATE practices SET active = false WHERE name = 'Old practice';
```

Changes take effect on the next scheduler tick (within 1 minute) — no restart needed.

### How to add or remove a practice mid-week

1. Edit `content/practices.yaml` (add/update/set `active: false`).
2. Re-seed: `python -m cli.seed practices content/practices.yaml --user-id <UID>`
3. No bot restart required — the scheduler reads the DB on every tick.

### How to upload new audio and get the file_id (audio subcommand)

1. Place the audio file on the server (e.g. `content/media/new_audio.mp3`).
2. Ensure the practice row already exists (seed it first if not).
3. Create or update `content/audio.yaml`:

```yaml
- name: Night hypnosis
  local_path: content/media/new_audio.mp3
  mime: audio/mpeg
```

4. Run the seeder (replace `<UID>` with the target user's Telegram ID):

```bash
python -m cli.seed audio content/audio.yaml --user-id <UID>
# Or via Docker (mount host content/ so media files and YAML are visible):
docker compose run --rm -v "$PWD/content:/app/content" bot python -m cli.seed audio content/audio.yaml --user-id <UID>
```

The seeder uploads the file to Telegram, captures the `file_id`, and stores it in
`media_assets`.  The practice row is updated to reference the new asset.

### How to upload new motivational images (images subcommand)

1. Place the image files on the server (e.g. `content/media/new_image.jpg`).
2. Create or update `content/images.yaml`:

```yaml
- local_path: content/media/new_image.jpg
  mime: image/jpeg
  active: true
```

3. Run the seeder (replace `<UID>` with the target user's Telegram ID):

```bash
python -m cli.seed images content/images.yaml --user-id <UID>
# Or via Docker (mount host content/ so media files and YAML are visible):
docker compose run --rm -v "$PWD/content:/app/content" bot python -m cli.seed images content/images.yaml --user-id <UID>
```

The seeder uploads the file, captures the `file_id`, and upserts a `media_assets` +
`motivational_images` row.  The scheduler will include the new image in the random pool
at 15:00 on the next day (AC-17).

---

## Cost monitoring (AC-16)

Monthly cost by type:

```sql
SELECT
    kind,
    model,
    COUNT(*) AS calls,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    ROUND(SUM(cost_usd)::numeric, 4) AS total_cost_usd
FROM api_usage_logs
WHERE created_at >= date_trunc('month', now())
GROUP BY kind, model
ORDER BY total_cost_usd DESC;
```

Total monthly spend:

```sql
SELECT ROUND(SUM(cost_usd)::numeric, 4) AS monthly_cost_usd
FROM api_usage_logs
WHERE created_at >= date_trunc('month', now());
```

The bot hard-stops analysis calls when the monthly total reaches `MONTHLY_COST_LIMIT_USD`
(default $10).  Each morning analysis is individually capped at `ANALYSIS_COST_CAP_USD`
(default $0.05, AC-11).

