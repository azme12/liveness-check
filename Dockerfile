# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LIVENESS_STORAGE_DIR=/app/storage \
    LIVENESS_MODELS_DIR=/app/models \
    LIVENESS_DATABASE_URL=sqlite+aiosqlite:///./data/liveness.db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install . \
    && mkdir -p /app/data /app/storage /app/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "liveness.api:app", "--host", "0.0.0.0", "--port", "8000"]
