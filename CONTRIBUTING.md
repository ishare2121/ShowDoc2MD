# Contributing

Contributions are welcome.

1. Create a virtual environment with Python 3.10+.
2. Install the project in editable mode: `python -m pip install -e .`.
3. Add or update tests for behavior changes.
4. Run `python -m unittest discover -s tests -v` before submitting a pull request.

## Test data rule

Use fake/example ShowDoc URLs, passwords and document contents in tests, issues and pull requests. Never commit private ShowDoc links, real document passwords, exported private documents, cookies, tokens or `.env` files.
