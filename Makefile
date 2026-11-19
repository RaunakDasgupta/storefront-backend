# Shortcuts. `make help` lists them.
PY ?= .venv/bin/python
FRONTEND_DIR ?= ../storefront-frontend

.PHONY: help install env migrate seed run dev test test-pg check-migrations new-migration all

help:
	@echo "make install            create .venv and install the dependencies"
	@echo "make env                create .env from .env.example (if there is none)"
	@echo "make migrate            bring the database up to date (alembic upgrade head)"
	@echo "make seed               add the demo accounts, products and orders to an empty database"
	@echo "make run                start the API on http://0.0.0.0:8000  (docs at /docs)"
	@echo "make dev                the same, restarting when the code changes"
	@echo "make all                start the API and the frontend together (FRONTEND_DIR=$(FRONTEND_DIR))"
	@echo "make test               run the tests on SQLite"
	@echo "make test-pg            run the tests on a real embedded Postgres"
	@echo "make check-migrations   fail if the models and the migrations disagree"
	@echo "make new-migration m='what changed'   generate a migration from the models"

install:
	python3 -m venv .venv || uv venv --python 3.12 .venv
	.venv/bin/python -m pip install -r requirements-dev.txt || uv pip install --python .venv/bin/python -r requirements-dev.txt

env:
	@test -f .env || (cp .env.example .env && echo "Created .env: set DATABASE_URL in it.")

migrate:
	$(PY) -m app.db.migrate

seed:
	$(PY) -m app.db.seed

run:
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

all:
	FRONTEND_DIR=$(FRONTEND_DIR) ./scripts/run-all.sh

test:
	$(PY) -m pytest

test-pg:
	TEST_WITH_POSTGRES=1 $(PY) -m pytest

check-migrations:
	$(PY) -m app.db.migrate --check

new-migration:
	$(PY) -m alembic revision --autogenerate -m "$(m)"
