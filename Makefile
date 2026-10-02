# Common tasks. Run `make help` for the list.
PYTHON ?= python3.11
VENV := .venv
PY := $(VENV)/bin/python
KIT_URL ?= http://localhost:8001

.PHONY: help setup test test-backend test-frontend lint check kit kit-replay benchmark dev up down seed-demo

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
	$(PY) -m pytest backend/tests -q -m "not integration"
	$(PY) -m pytest eval/test_judge.py eval/tests -q

test-frontend:
	cd frontend && npm test

lint:  ## ruff + eslint
	$(VENV)/bin/ruff check .
	cd frontend && npm run lint

check: lint test  ## Everything CI runs before deploying
	cd frontend && npm run build

kit:  ## Parcel kit: run the 7-parcel answer key against a live backend (KIT_URL, default :8001); chat costs ~$1
	PYTHONPATH=. $(PY) -m eval.parcel_kit --full $(KIT_URL) --out-dir eval/results/$$(date +%F)

kit-replay:  ## Parcel kit: re-score the recorded 2026-10-01 runs (no network, no cost)
	PYTHONPATH=. $(PY) -m eval.parcel_kit --replay eval/kit/baseline/2026-10-01 --out-dir /tmp/parcel-kit-replay

benchmark:  ## Regenerate docs/benchmark/ (the public parcel-kit page) from the committed results
	PYTHONPATH=. $(PY) -m eval.benchmark

dev:  ## Qdrant in Docker, backend on :8001, frontend on :5173 (Ctrl-C stops both)
	docker compose up -d qdrant
	trap 'kill 0' EXIT; \
	$(VENV)/bin/uvicorn backend.main:app --reload --port 8001 & \
	(cd frontend && npm run dev) & \
	wait

seed-demo:  ## Embed the committed zoning-code sample (Titles 16-17) into an empty local Qdrant
	docker compose up -d qdrant
	$(PY) -m ingestion.embed_and_store --chunks ingestion/sample/chunks_t16_17.jsonl.gz

up:  ## Full stack in Docker (nginx frontend on :80; set FRONTEND_PORT to change)
	docker compose -f docker-compose.yml up --build

down:  ## Stop the Docker stack
	docker compose -f docker-compose.yml down
