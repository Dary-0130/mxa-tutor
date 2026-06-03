.PHONY: install dev test lint format type-check hygiene check clean

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn api.main:app --reload --port 8000

test:
	pytest -v

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

type-check:
	mypy core/ adapters/ features/ api/

hygiene:
	bash scripts/check_repo_hygiene.sh

check: lint type-check test hygiene
	@echo "All checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
