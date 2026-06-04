## Project

Install all dependencies:
`pip install -e .[dev]`

Only prod deps:
`pip install -e .`

Install git hook:
`pre-commit install`

Launch project:
`python cli.py`

Launch git hooks without commit:
`pre-commit run --all-files`

## Tests

Launch all tests:
`pytest`

Launch unit tests:
`pytest tests/unit/`

## Linter ruff

Check the project:
`ruff check .`

Auto-fix
`ruff check . --fix`