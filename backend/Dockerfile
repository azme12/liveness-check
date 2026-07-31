# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app \
    LIVENESS_STORAGE_DIR=/app/storage \
    LIVENESS_MODELS_DIR=/app/models \
    LIVENESS_OPENFACE_AUTO_DETECT=false \
    LIVENESS_OPENFACE_ENABLED=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY app ./app
COPY models ./models
COPY tests ./tests

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -e . \
    && mkdir -p /app/storage /app/models

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8100}/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8100}
