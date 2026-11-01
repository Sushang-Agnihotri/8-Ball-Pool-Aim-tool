# Contributing

1. Fork and create a branch.
2. `pip install -e ".[dev]"`
3. Make changes; keep pure logic in `geometry.py`/`config.py` with tests.
4. Run `ruff check . && ruff format . && pytest && bandit -r src` before opening a PR.
5. Describe the change and how you tested it.
