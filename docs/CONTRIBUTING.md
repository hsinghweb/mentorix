# Contributing to Mentorix

Thank you for your interest in contributing! Here's how to get started.

## Getting Started

1. **Fork & clone** the repository
2. **Set up** the development environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   docker compose up -d
   make dev
   ```
3. **Install pre-commit hooks**: `pre-commit install`

## Branch Naming

| Type | Format | Example |
|------|--------|---------|
| Feature | `feature/<short-slug>` | `feature/agent-circuit-breakers` |
| Bug fix | `fix/<short-slug>` | `fix/diagnostic-freeze` |
| Refactor | `refactor/<short-slug>` | `refactor/learning-package-split` |
| Docs | `docs/<short-slug>` | `docs/api-versioning` |

## Pull Request Guidelines

1. **One concern per PR** — avoid bundling unrelated changes
2. **Write a clear title** — e.g., "feat: add CSRF middleware" or "fix: diagnostic test selector"
3. **Include context** in the PR description:
   - What problem does this solve?
   - What approach did you take?
   - Any trade-offs or alternatives considered?
4. **Add/update tests** for any logic changes
5. **Ensure CI passes** — run `make lint` and `make test` locally before pushing

## Code Style

- **Python**: Follows [ruff](https://docs.astral.sh/ruff/) defaults. Run `make lint` to check.
- **JavaScript**: Vanilla JS, no framework. Follow existing patterns in `app.js`.
- **CSS**: Vanilla CSS with CSS custom properties. Follow existing variable naming in `styles.css`.
- **Naming**: See [NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md) for full details.

## Testing Requirements

- All new Python modules need unit tests in `API/tests/`
- Run `make test` (or `scripts/test_fast.sh`) before submitting
- Integration tests should use the `TestClient` from FastAPI
- Frontend changes should be manually tested in Chrome and Firefox

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for system overview and data flow diagrams.

## Questions?

Open an issue or reach out to the maintainers.
