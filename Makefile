SRC        = src/dvc_databricks
TESTS      = tests
DOCS       = docs
DOCS_BUILD = docs/_build/html

.DEFAULT_GOAL := help

.PHONY: help install test lint docs docs-serve clean

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install     Install the package with all dev dependencies"
	@echo "  test        Run tests with coverage report"
	@echo "  lint        Run pylint on the source package"
	@echo "  docs        Build Sphinx HTML documentation"
	@echo "  docs-serve  Serve the built docs at http://localhost:8000"
	@echo "  clean       Remove build artifacts, coverage data, and docs build"

install:
	uv sync --extra dev

test:
	uv run pytest $(TESTS) \
	  --cov=dvc_databricks \
	  --cov-report=term-missing \
	  --cov-report=html:htmlcov \
	  -v

lint:
	uv run pylint $(SRC)

docs:
	uv run sphinx-apidoc -f -o $(DOCS)/api $(SRC)
	uv run sphinx-build -b html $(DOCS) $(DOCS_BUILD)
	@echo ""
	@echo "Documentation built → $(DOCS_BUILD)/index.html"

docs-serve: docs
	uv run python -m http.server 8000 --directory $(DOCS_BUILD)

clean:
	rm -rf dist/ build/ $(DOCS_BUILD) htmlcov/ .coverage .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
