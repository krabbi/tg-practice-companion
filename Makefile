.PHONY: run test lint format coverage install \
        frontend-install frontend-lint frontend-typecheck frontend-test frontend-build frontend-check

install:
	pip install -e ".[dev]"
	pre-commit install

run:
	python -m bot

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

# Meaningful only once bot/ has real modules (bootstrap bypass — see CLAUDE.md).
# Runs the overall ≥80% gate AND the per-file ≥80% gate (scripts/check_coverage.py).
coverage:
	pytest --cov=bot --cov-report=term-missing --cov-report=json --cov-fail-under=80
	python scripts/check_coverage.py

# --- Frontend (Vue 3 + Vite SPA, frontend/) ---
# Mandatory gates: typecheck, test (Vitest), build. lint (ESLint) recommended.
# No numeric coverage gate on the SPA — the pr-reviewer judges test adequacy.
frontend-install:
	cd frontend && npm ci

frontend-lint:
	cd frontend && npm run lint --if-present

frontend-typecheck:
	cd frontend && npm run typecheck

frontend-test:
	cd frontend && npm test

frontend-build:
	cd frontend && npm run build

frontend-check: frontend-lint frontend-typecheck frontend-test frontend-build
