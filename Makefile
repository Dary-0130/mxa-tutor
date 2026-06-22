.PHONY: install dev test test-engine lint format type-check hygiene check clean export-schema verify-schema

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn api.main:app --reload --port 8000

test:
	pytest -v

test-engine:
	python -c "import os, subprocess, sys; from pathlib import Path; win = Path('.venv/Scripts/python.exe'); posix = Path('.venv/bin/python'); exe = str(win if win.exists() else posix if posix.exists() else Path(sys.executable)); env = os.environ.copy(); env['MXA_RUN_MATLAB_ENGINE'] = '1'; raise SystemExit(subprocess.call([exe, '-m', 'pytest', '-v', 'tests/adapters/matlab_engine/test_runtime_integration.py'], env=env))"

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
	python -m scripts.export_bridge_schemas

verify-schema: export-schema
	@git diff --exit-code schemas/project_overview.schema.json \
		|| (echo "schemas/project_overview.schema.json drifted. Regenerate with 'make export-schema' and commit." && exit 1)
	@git diff --exit-code schemas/bridge_diagnostic_request.schema.json \
		schemas/bridge_diagnostic_receipt.schema.json \
		schemas/bridge_error_response.schema.json \
		schemas/bridge_explanation_request.schema.json \
		schemas/bridge_explanation_result.schema.json \
		schemas/bridge_explanation_error.schema.json \
		|| (echo "bridge schemas drifted. Regenerate with 'make export-schema' and commit." && exit 1)
