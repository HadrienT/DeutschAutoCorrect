# 8000 is commonly taken by local LLM servers (llama.cpp, vLLM): the API listens on 8010.
PORT ?= 8010
export DAC_API_PORT = $(PORT)
# Use backend/.venv when it exists, without having to activate it.
PY := $(if $(wildcard backend/.venv/bin/python),.venv/bin/python,python)

.PHONY: install dev-back dev-front test test-back test-front lint build demo up down logs
install:
	cd backend && $(PY) -m pip install -e ".[dev]"
	cd frontend && npm ci
dev-back:
	cd backend && $(PY) -m uvicorn app.main:app --reload --port $(PORT)
dev-front:
	cd frontend && npm run dev
test: test-back test-front
test-back:
	cd backend && $(PY) -m pytest -q
test-front:
	cd frontend && npm test
lint:
	cd backend && $(PY) -m ruff check app tests
	cd frontend && npm run lint
build:
	cd frontend && npm run build
demo:
	cd backend && DAC_DATA_DIR=../data $(PY) -m app.seed_demo && \
	DAC_DATA_DIR=../data DAC_ASR_BACKEND=mock DAC_PRON_BACKEND=mock DAC_CORRECTOR_BACKEND=rules $(PY) -m uvicorn app.main:app --port $(PORT)
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f app
