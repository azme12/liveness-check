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

## Deploy (production)

| Component | Host | Notes |
|-----------|------|--------|
| **Frontend** | [Vercel](https://vercel.com) | Root directory: `frontend` |
| **Backend** | Railway, Render, Fly.io, or VPS | FastAPI + long-running process |
| **Database** | [MongoDB Atlas](https://www.mongodb.com/atlas) | Connection string for backend |

### Vercel (frontend)

1. Import repo `azme12/liveness-check`.
2. Set **Root Directory** to `frontend`.
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = public backend URL (e.g. `https://api.yourdomain.com`)
4. Deploy. Do not use `127.0.0.1` — the browser must reach your API over HTTPS.

### Backend + MongoDB

On your backend host, set at minimum:

```bash
LIVENCUBE_MONGODB_URL=mongodb+srv://...   # Atlas
LIVENCUBE_JWT_SECRET=<strong-random-secret>
LIVENCUBE_CORS_ORIGINS=https://your-app.vercel.app
LIVENESS_MONGODB_URL=mongodb+srv://...
```

Start with: `uvicorn app.main:app --host 0.0.0.0 --port 8100`

## Layout

| Path | Purpose |
|------|---------|
| `frontend/` | Login, Home, Clients, Sessions, Checks, Workflows, Integration |
| `backend/app/` | Dashboard API (auth, workflows, webhooks, …) |
| `backend/src/liveness/` | Verification engine (`/v1/clients`, `/v1/checks`, …) |
| `backend/tests/` | Pytest suite |
