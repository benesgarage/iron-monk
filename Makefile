.DEFAULT_GOAL := help

.PHONY: help install test cov lint format typecheck check clean build

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install the package in editable mode with development dependencies
	python -m pip install -e ".[dev]"

test: ## Run the test suite (coverage is configured in pyproject.toml)
	pytest

cov: ## Run the test suite and generate a coverage report
	pytest --cov=monk --cov-report=term-missing

lint: ## Run the Ruff linter
	ruff check .

format: ## Run the Ruff formatter
	ruff format .

typecheck: ## Run the MyPy type checker
	mypy src/monk tests

check: format lint typecheck test ## Run all formatters, linters, type checks, and tests

clean: ## Clean up build artifacts, cache directories, and compiled files
	rm -rf build/ dist/ *.egg-info/ src/*.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

build: clean ## Build the package (sdist and wheel) for publishing
	python -m build