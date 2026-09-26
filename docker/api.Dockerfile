# ---- Build stage ----
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only dependency files first (cache layer).
# --no-install-project: hatchling would otherwise require README.md + source
# at this stage; we copy the app in the runtime image and run via uvicorn.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Runtime stage ----
FROM python:3.12-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Create cache directory for FastEmbed model (persisted via volume in compose if needed)
RUN mkdir -p /app/.fastembed_cache && chown -R appuser:appuser /app
ENV FAST_EMBED_CACHE_DIR=/app/.fastembed_cache

# Switch to non-root user
USER appuser

# Path to venv python
ENV PATH="/app/.venv/bin:$PATH"

# Expose port (Traefik will route to this)
EXPOSE 8000

# Run the API
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]