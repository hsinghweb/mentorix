# Contributing to Mentorix

Thank you for contributing! Follow these guidelines to keep the project healthy.

## Branch Naming

- Feature: `feature/<short-description>`
- Bug fix: `fix/<short-description>`
- Docs: `docs/<short-description>`

## PR Guidelines

1. **One feature or fix per PR** — keep changes focused.
2. **Write a clear description** — explain *what* changed and *why*.
3. **Reference the task** — link to the planner item (e.g. `Closes Sec 2.4`).
4. **Test your changes** — run `make test` before submitting.
5. **Keep PRs small** — under 400 lines of diff when possible.

## Code Style

- **Python**: Follow PEP 8. Use type annotations on all public functions.
- **JavaScript**: Use `const`/`let`, template literals, and descriptive variable names.
- **CSS**: Use the design system variables from `styles.css`.

## Running Locally

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start services
docker-compose up -d  # PostgreSQL, Redis, MongoDB

# Run API
cd API && uvicorn app.main:app --reload --port 8000

# Frontend (static files)
cd frontend && python -m http.server 5500
```

## Testing

```bash
# Run fast tests
python scripts/test_fast.py

# Run full test suite
python scripts/test_full.py
```

## Commit Messages

Use imperative mood: "Add feature" not "Added feature".

Format: `<type>: <description>`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
