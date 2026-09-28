# Common tasks. Run `make help` for the list.
PYTHON ?= python3.11
VENV := .venv
PY := $(VENV)/bin/python

.PHONY: help setup test test-backend test-frontend lint check dev up down

help:  ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup:  ## Create .venv, install backend + frontend deps, copy env examples
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt
	cd frontend && npm ci
	@test -f .env || cp .env.example .env
	@test -f frontend/.env || cp frontend/.env.example frontend/.env

test: test-backend test-frontend  ## Run all unit tests (no network, keys, or Qdrant needed)

test-backend:
	$(PY) -m pytest backend/tests eval/test_judge.py -q -m "not integration"

test-frontend:
	cd frontend && npm test

lint:  ## ruff + eslint
	$(VENV)/bin/ruff check .
	cd frontend && npm run lint

check: lint test  ## Everything CI runs before deploying
	cd frontend && npm run build

dev:  ## Qdrant in Docker, backend on :8001, frontend on :5173 (Ctrl-C stops both)
	docker compose up -d qdrant
	trap 'kill 0' EXIT; \
	$(VENV)/bin/uvicorn backend.main:app --reload --port 8001 & \
	(cd frontend && npm run dev) & \
	wait

up:  ## Full stack in Docker (nginx frontend on :80; set FRONTEND_PORT to change)
	docker compose -f docker-compose.yml up --build

down:  ## Stop the Docker stack
	docker compose -f docker-compose.yml down
