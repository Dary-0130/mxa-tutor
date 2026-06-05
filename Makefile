.PHONY: install dev test lint format type-check hygiene check clean export-schema verify-schema

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
	python scripts/check_repo_hygiene.py

check: lint type-check test hygiene
	@echo "All checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache

export-schema:
	python -m scripts.export_overview_schema

verify-schema: export-schema
	@git diff --exit-code schemas/project_overview.schema.json \
		|| (echo "schemas/project_overview.schema.json drifted. Regenerate with 'make export-schema' and commit." && exit 1)
