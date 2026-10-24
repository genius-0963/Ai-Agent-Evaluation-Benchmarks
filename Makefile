.PHONY: install lint format test test-unit test-integration smoke-test validate clean build-bench run-scripted run-noop

VENV ?= .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
AGENTBENCH = $(VENV)/bin/agentbench

install:
	uv pip install --python $(PYTHON) -e ".[dev]"

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

test: test-unit

test-unit:
	$(PYTEST) tests/unit -v

test-integration:
	$(PYTEST) tests/integration -v

validate:
	$(PYTHON) scripts/validate_benchmarks.py

smoke-test:
	./scripts/smoke_test.sh

build-bench:
	$(AGENTBENCH) build config-recovery-001

run-scripted:
	$(AGENTBENCH) run config-recovery-001 --agent scripted

run-noop:
	$(AGENTBENCH) run config-recovery-001 --agent noop

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
