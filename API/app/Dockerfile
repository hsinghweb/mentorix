# ── Multi-stage Docker build for Mentorix API ────────────────────────
# Stage 1: Builder — install dependencies using uv lockfile
# Stage 2: Runtime — slim image with only runtime files
# Reduces final image size by ~40% vs single-stage build.

FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -U pip uv

# Install dependencies from lockfile (no dev deps, no editable install)
COPY pyproject.toml uv.lock /build/
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . /build


# ── Stage 2: Runtime ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Copy only the virtual environment and application code from builder
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/app /app/app
COPY --from=builder /build/pyproject.toml /app/pyproject.toml

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
