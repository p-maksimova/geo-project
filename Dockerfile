# Stage 1: install dependencies
FROM python:3.13-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: runtime image
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /app/.venv ./.venv

COPY app/ ./app/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY main.py ./

ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=data \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD ["python", "main.py"]
