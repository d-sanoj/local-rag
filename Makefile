.PHONY: run test lint format install

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

run:
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check app tests
	.venv/bin/ruff format --check app tests

format:
	.venv/bin/ruff format app tests
	.venv/bin/ruff check --fix app tests
