# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app \
    LIVENESS_STORAGE_DIR=/app/storage \
    LIVENESS_MODELS_DIR=/app/models \
    LIVENESS_OPENFACE_AUTO_DETECT=false \
    LIVENESS_OPENFACE_ENABLED=false \
    LIVENESS_INSIGHTFACE_ENABLED=false \
    LIVENESS_STRICT_PRODUCTION=true \
    LIVENESS_MEDIAPIPE_ENABLED=true

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY app ./app
COPY models ./models
COPY tests ./tests

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && mkdir -p /app/storage /app/models \
    && curl -fsSL -o /app/models/face_detection_yunet_2023mar.onnx \
      "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" \
    && curl -fsSL -o /app/models/face_recognition_sface_2021dec.onnx \
      "https://huggingface.co/opencv/opencv_zoo/resolve/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx" \
    && curl -fsSL -o /app/models/face_landmarker.task \
      "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task" \
    && mkdir -p /app/models/liveness \
    && curl -fsSL -o /app/models/liveness/minifas_v2.onnx \
      "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx"

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8100}/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8100}
