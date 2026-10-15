# Contributing

Thanks for improving **agentic-browser** (Python package / import: `agent_browser`).

## Setup

```bash
git clone https://github.com/applejuice093/Agentic-browser.git
cd Agentic-browser
git checkout main

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev,mcp]"
playwright install chromium
cp .env.example .env        # optional; never commit .env
```

Or use the Makefile:

```bash
make install
# then: .venv/bin/playwright install chromium
make test-unit
make test
```

## Branches

- Work on a feature branch; do **not** commit directly to `main`.
- Historical milestone branches (`milestone/m*`) are complete; prefer short-lived topic branches.

## Tests & lint

```bash
pytest -q
ruff check src tests examples
```

Unit helpers (config, exceptions, compact observation, stable IDs) should run without a network browser when possible. Prefer mocks for Playwright/network in new unit tests.

## Examples

Scripts under `examples/` should:

- Include a short module docstring with run instructions
- Read secrets from the environment (see `.env.example`) — never hardcode API keys
- Prefer offline HTML (`browser.set_content`) when demonstrating core APIs

## Packaging notes

| Item | Value |
|------|--------|
| PyPI name | `agentic-browser` |
| Import | `agent_browser` |
| CLIs | `agent-browser`, `agent-browser-mcp` |

Keep `requirements.txt` comments aligned with `pyproject.toml` extras.

## License

By contributing you agree that your contributions are licensed under the MIT License (see [LICENSE](./LICENSE)).
