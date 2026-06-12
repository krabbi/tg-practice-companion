.PHONY: run test lint format coverage install

install:
	pip install -e ".[dev]"

run:
	python -m bot

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

# Meaningful only once bot/ has real modules (bootstrap bypass — see CLAUDE.md).
coverage:
	pytest --cov=bot --cov-report=term-missing --cov-fail-under=80
