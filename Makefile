.PHONY: install dev lint test test-unit test-integration test-eval run worker migrate seed docker-up docker-down clean

# Installation
install:
	pip install .

dev:
	pip install ".[dev]"

# Code quality
lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	ruff format src/ tests/

# Testing
test:
	pytest tests/ -v --cov=src

test-unit:
	pytest tests/unit/ -v --cov=src

test-integration:
	pytest tests/integration/ -v -m integration

test-eval:
	pytest tests/eval/ -v -m eval

# Run services
run:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A src.tasks.celery_app worker --loglevel=info --concurrency=4

# Database
migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(msg)"

seed:
	python scripts/seed_db.py

# Docker
docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

docker-build:
	docker-compose -f docker/docker-compose.yml build

docker-test:
	docker-compose -f docker/docker-compose.test.yml up -d
	pytest tests/ -v
	docker-compose -f docker/docker-compose.test.yml down

# Eval
eval:
	python scripts/run_eval.py

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
