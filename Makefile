.PHONY: run test lint format install

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

run:
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	.venv/bin/pytest -q

smoke:
	.venv/bin/python scripts/smoke_test.py

lint:
	.venv/bin/ruff check app tests scripts streamlit_app
	.venv/bin/ruff format --check app tests scripts streamlit_app

format:
	.venv/bin/ruff format app tests scripts streamlit_app
	.venv/bin/ruff check --fix app tests scripts streamlit_app
