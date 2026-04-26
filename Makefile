.PHONY: install install-dev test coverage lint pylint clean

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest

coverage:
	$(PYTHON) -m pytest --cov=main --cov-report=term-missing --cov-fail-under=85

lint:
	$(PYTHON) -m ruff check .

pylint:
	$(PYTHON) -m pylint main.py tests/

clean:
	rm -rf .pytest_cache .coverage __pycache__ tests/__pycache__
