#!/usr/bin/env bash
# Download optional ONNX weights into ./models
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/models/liveness"

OUT="$ROOT/models/liveness/minifas_v2.onnx"
URL="https://github.com/QingHeYang/Silent-Face-Anti-Spoofing-onnx/raw/main/onnx/2.7_80x80_MiniFASNetV2.onnx"

if [[ -f "$OUT" ]]; then
  echo "Already exists: $OUT"
  exit 0
fi

echo "Downloading MiniFASNet V2 → $OUT"
curl -L --fail -o "$OUT" "$URL"
echo "Done. InsightFace buffalo_l downloads automatically on first use."
