## Project

Install all dependencies:
`pip install -e .[dev]`

Only prod deps:
`pip install -e .`

Launch project:
`python cli.py`

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
ruff format .           # отформатировать (как black)