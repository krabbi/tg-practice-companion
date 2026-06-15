# orchestration.md — Multi-agent pipeline reference

How the multi-agent pipeline runs: who does what, the staged review/merge gates,
the dev-subscription budget. **This is orchestration meta — it is NOT needed to
implement a single issue.** The autonomous coder (`claude-issue.yml`) must not read
this file: its job ends at "open PR", and review/product-acceptance/merge are owned
by separate staged workflows, not by the implementing agent. Read this when you are
orchestrating (`/implement-task`), reviewing, or reasoning about the merge gates.

For the quick summary see `CLAUDE.md`.

---

## Two budgets — never confuse them

1. **Product runtime budget** ($5–10/month API, AC-16): the bot's own Haiku/Whisper calls in
   production. Controlled by product code (token logging, cost guardrails). The actionable
   per-task constraint lives in `CLAUDE.md` → Project-specific guardrails (Cost logging).
2. **Dev subscription** (Claude Code Pro): the budget agents spend writing code. Controlled by
   this infrastructure (compact context, inline issue/diff passing, sonnet agents).

---

## Agent workflow

Three specialized subagents — all `model: sonnet`. Use them in this order for every
non-trivial feature.

| Agent | Role |
|---|---|
| `product-manager` | Requirements, edge cases, GitHub issue creation, product acceptance review |
| `coder` | End-to-end implementation: code + tests + docs, drives PR to merge |
| `pr-reviewer` | Code review: architecture, tests, security, linting, docs coverage |

### Standard flow

```
1. product-manager  →  clarifies requirements, creates GitHub issues
2. coder            →  implements (code + tests + docs), creates PR
3. pr-reviewer      →  code review; CHANGES_REQUESTED → coder fixes → re-review
4. product-manager  →  product acceptance review (ONLY if docs/user_guide.md changed)
                        PRODUCT CHANGES REQUESTED → coder fixes → back to step 3
5. gh pr merge --squash --delete-branch
```

### Large features: human-triggered ralplan only

For large or risky **architecture forks**, the OPERATOR manually runs
`/oh-my-claudecode:ralplan` BEFORE creating issues. Agents (product-manager,
`/implement-task`) never invoke ralplan/team/autopilot themselves. On the Pro
subscription ralplan defaults to Opus and burns the weekly cap — it is an
occasional luxury, not a routine step.

### Merge gates

- Every PR needs `pr-reviewer` **APPROVED** before merge.
- PRs that change `docs/user_guide.md` also need `product-manager` **PRODUCT APPROVED**.
- The PR's CI checks must be **green** before merge (`gh pr checks <N> --watch --fail-fast`) —
  local test runs can silently skip CI-only tests (the suite runs against real Postgres in CI
  but sqlite locally, and pytest versions differ — never declare "tests pass" from a local run).
- **There is NO branch protection on `main`.** GitHub branch protection / rulesets require a paid
  plan or a public repo; this repo is private on the free plan, so the API returns 403 and no
  enforced gate exists. The merge gates above are enforced **only** by the staged label-driven
  workflows — nothing at the git level stops a direct push or an agent self-merge. Therefore the
  implementing agent (`claude-issue.yml`, `claude-sweeper.yml`) must stop at "open PR" and never
  merge/close PRs itself (enforced via prompt + `--disallowedTools`); merge happens solely in
  `claude-pr-merge.yml` after the CI gate.
- Merge is owned by the orchestrator (`/implement-task`); the coder agent merges only
  when invoked standalone and never when told "do not merge".

### Product questions during implementation

- **Significant** (UX, data model, scope) → consult `product-manager` agent.
- **Minor** (naming, log level, internal detail) → decide and note in a comment.
