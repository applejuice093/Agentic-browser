# Agentic Browser — common developer tasks
# Prefer: make install && make test

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

.PHONY: help venv install install-mcp install-all test test-unit lint example-basic example-agent clean

help:
	@echo "Targets:"
	@echo "  make install       Create .venv and pip install -e '.[dev]'"
	@echo "  make install-mcp   Install with MCP extras"
	@echo "  make install-all   Install all extras"
	@echo "  make test          Run full pytest suite"
	@echo "  make test-unit     Pure helpers (no browser if skipped by suite)"
	@echo "  make lint          Ruff check on src/tests/examples"
	@echo "  make example-basic Run examples/basic_open.py"
	@echo "  make example-agent Run examples/agent_loop_demo.py"
	@echo "  make clean         Remove caches and build artifacts"

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -e ".[dev]"
	@echo "Next: $(VENV)/bin/playwright install chromium"

install-mcp: venv
	$(PIP) install -e ".[dev,mcp]"

install-all: venv
	$(PIP) install -e ".[all]"

test:
	$(PYTEST) -q

test-unit:
	$(PYTEST) -q tests/test_config.py tests/test_exceptions.py tests/test_observation_compact.py tests/test_stable_ids.py tests/test_models.py

lint:
	$(RUFF) check src tests examples

example-basic:
	$(VENV)/bin/python examples/basic_open.py

example-agent:
	$(VENV)/bin/python examples/agent_loop_demo.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml dist build *.egg-info
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
