# Trustanova / Liveness

ComplyCube-style identity verification platform.

```
liveness/
  frontend/   # Next.js dashboard (port 3000)
  backend/    # FastAPI — dashboard + verification checks (port 8100)
```

## Quick start

```bash
# MongoDB
docker compose up -d mongo

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
LIVENCUBE_MONGODB_URL=mongodb://127.0.0.1:27018 \
LIVENESS_MONGODB_URL=mongodb://127.0.0.1:27018 \
uvicorn app.main:app --reload --port 8100

# Frontend
cd ../frontend
npm install
npm run dev
```

- **UI:** http://127.0.0.1:3000  
- **API docs:** http://127.0.0.1:8100/docs  
- **Demo login:** `admin@trustanova.dev` / `admin123`  
- **Checks API key:** `sk_test_liveness_dev` (`X-Api-Key`)

## Docker (all)

```bash
docker compose up --build -d
```

## Layout

| Path | Purpose |
|------|---------|
| `frontend/` | Login, Home, Clients, Sessions, Checks, Workflows, Integration |
| `backend/app/` | Dashboard API (auth, workflows, webhooks, …) |
| `backend/src/liveness/` | Verification engine (`/v1/clients`, `/v1/checks`, …) |
| `backend/tests/` | Pytest suite |
