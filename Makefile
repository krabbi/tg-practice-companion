.PHONY: run test lint format coverage install

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
