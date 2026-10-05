.PHONY: install dev-back dev-front test test-back test-front lint build demo
install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm ci
dev-back:
	cd backend && uvicorn app.main:app --reload --port 8000
dev-front:
	cd frontend && npm run dev
test: test-back test-front
test-back:
	cd backend && python -m pytest -q
test-front:
	cd frontend && npm test
lint:
	cd backend && ruff check app tests
	cd frontend && npm run lint
build:
	cd frontend && npm run build
demo:
	cd backend && DAC_DATA_DIR=../data python -m app.seed_demo && \
	DAC_DATA_DIR=../data DAC_ASR_BACKEND=mock DAC_PRON_BACKEND=mock uvicorn app.main:app --port 8000
