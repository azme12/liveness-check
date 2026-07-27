# Liveness

**Open-source identity verification & compliance platform** — document OCR, passive liveness, face matching, and AML hooks.

Built with **FastAPI 0.140+**, Python 3.11+, and optional open-source ML backends (PaddleOCR, InsightFace, MiniFAS ONNX).

---

## What you get (Phase 1)

| Capability | Status | Backend |
|------------|--------|---------|
| Checks API (async) | ✅ | FastAPI 0.140 |
| `document_check` | ✅ | OpenCV quality + PaddleOCR (optional) |
| `identity_check` | ✅ | MiniFAS / heuristic liveness + InsightFace / Haar face match |
| `standard_screening_check` | ✅ demo | Blocklist stub (hook yente next) |
| Capture sessions | ✅ | Session tokens for SDKs |
| Clients / documents / live photos | ✅ | SQLite (Postgres-ready) |

Heavy ML packages are **optional**. Without them the library uses heuristics so you can develop the API immediately.

---

## Quick start

```bash
# Create venv + install (core API)
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run API
cp .env.example .env
liveness serve --reload
# → Swagger UI:  http://127.0.0.1:8000/docs
# → ReDoc:       http://127.0.0.1:8000/redoc
# → OpenAPI:     http://127.0.0.1:8000/openapi.json
```

Default API key: `sk_test_liveness_dev` (header `X-Api-Key` — use **Authorize** in Swagger).

### Optional ML extras

```bash
pip install -e ".[bio]"   # InsightFace + ONNX Runtime (face + MiniFAS)
pip install -e ".[doc]"   # PaddleOCR 3.x
pip install -e ".[all]"   # everything
```

Place MiniFAS weights at:

```text
models/liveness/minifas_v2.onnx
```

(Download from [Silent-Face-Anti-Spoofing ONNX](https://github.com/QingHeYang/Silent-Face-Anti-Spoofing-onnx).)

---

## Library usage

```python
from liveness.checks import CheckEngine, CheckContext
from liveness.ml import decode_image
from liveness.types import CheckType

engine = CheckEngine()
doc = decode_image(open("passport.jpg", "rb").read())
selfie = decode_image(open("selfie.jpg", "rb").read())

result = engine.run(
    CheckType.IDENTITY,
    CheckContext(document_image=doc, live_photo_image=selfie),
)
print(result.outcome, result.biometric)
```

---

## API flow (ComplyCube-style)

```bash
# 1. Create client
curl -s -X POST http://127.0.0.1:8000/v1/clients \
  -H "X-Api-Key: sk_test_liveness_dev" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","full_name":"Ada Lovelace"}'

# 2. Upload document + selfie (multipart)
# 3. Create check
curl -s -X POST http://127.0.0.1:8000/v1/checks \
  -H "X-Api-Key: sk_test_liveness_dev" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id":"cli_...",
    "type":"identity_check",
    "document_id":"doc_...",
    "live_photo_id":"pho_...",
    "client_consent":true
  }'

# 4. Poll GET /v1/checks/{id} until status=complete
```

Interactive docs: **Swagger** http://127.0.0.1:8000/docs · **ReDoc** http://127.0.0.1:8000/redoc

---

## Project layout

```text
src/liveness/
  api/          # FastAPI app, routes, worker
  checks/       # CheckEngine (document / identity / screening)
  ml/           # quality, liveness, face, OCR adapters
  types.py      # CheckType, outcomes, structured dates
  db.py         # SQLAlchemy models
  storage.py    # local blob store (swap for S3/MinIO)
  cli.py        # `liveness serve`
tests/
docker-compose.yml
Dockerfile
```

---

## Stack (latest open source)

| Component | Package |
|-----------|---------|
| API | `fastapi>=0.140.0` |
| Validation | `pydantic>=2.11` |
| Server | `uvicorn` |
| DB | SQLAlchemy 2 + aiosqlite (Postgres via `asyncpg` later) |
| Vision | OpenCV, Pillow, NumPy |
| Face (optional) | InsightFace `buffalo_l` |
| Liveness (optional) | MiniFAS ONNX via onnxruntime |
| OCR (optional) | PaddleOCR ≥ 3.0 |
| AML (next) | [yente](https://github.com/opensanctions/yente) / OpenSanctions |

---

## Docker (all data inside Docker volumes)

```bash
docker compose up --build -d

# Swagger UI  → http://127.0.0.1:8000/docs
# Health      → http://127.0.0.1:8000/health
# DB tables   → http://127.0.0.1:8080   (sqlite-web)
```

```bash
docker compose logs -f api
docker compose down
```

API key (default): `sk_test_liveness_dev` — override with `LIVENESS_API_KEY`.

SQLite lives in Docker volume `liveness-data` at `/app/data/liveness.db` (not on your host project folder).

### View tables (Docker)

**Browser:** http://127.0.0.1:8080

**CLI:**

```bash
docker exec -it liveness-api python -c "
import sqlite3
c = sqlite3.connect('/app/data/liveness.db')
print(c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())
print(c.execute('SELECT * FROM clients').fetchall())
"
```

---

## Tests

```bash
pytest -q
```

---

## Roadmap

- [x] Phase 1 core library + Checks API
- [ ] Presigned S3/MinIO uploads
- [ ] yente AML worker
- [ ] Video / enhanced identity
- [ ] Web capture SDK
- [ ] Webhooks with HMAC

---

## License

Apache-2.0 — see [LICENSE](LICENSE).

Model weights (InsightFace, MiniFAS, PaddleOCR) have their own licenses — check before commercial use.
