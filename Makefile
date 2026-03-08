.PHONY: dev test lint db-migrate docker-up docker-down fmt

# ── Development ──
dev:
	cd API && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && python -m http.server 5500

# ── Testing ──
test:
	cd API && python -m pytest tests/ -x -q

test-fast:
	python scripts/test_fast.py

test-full:
	python scripts/test_full.py

# ── Linting ──
lint:
	cd API && python -m ruff check app/

fmt:
	cd API && python -m ruff format app/

typecheck:
	cd API && python -m mypy app/ --ignore-missing-imports

# ── Database ──
db-migrate:
	cd API && alembic upgrade head

db-reset:
	cd API && alembic downgrade base && alembic upgrade head

# ── Docker ──
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f --tail=100

# ── Helpers ──
seed:
	cd API && python scripts/seed_test_data.py

health:
	curl -s http://localhost:8000/health | python -m json.tool
