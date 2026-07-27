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

### Vercel (frontend + backend together)

The repo includes a root [`vercel.json`](vercel.json) for **Vercel Services** (Next.js + FastAPI on one domain).

1. Import repo → **Application Preset: Services**
2. Click **Refresh** after `vercel.json` is on `main`
3. In **Project → Settings → Environment Variables**, add:
   - `LIVENCUBE_MONGODB_URL` / `LIVENESS_MONGODB_URL` → MongoDB Atlas URI
   - `LIVENCUBE_JWT_SECRET` → strong secret
   - `LIVENCUBE_CORS_ORIGINS` → your Vercel URL (e.g. `https://liveness-check.vercel.app`)
4. Deploy. API routes go to `/api/*` on the same domain (no `NEXT_PUBLIC_API_URL` needed).

**MongoDB Atlas is required** — Vercel has no built-in MongoDB.

### Vercel (frontend only)

If you prefer frontend-only on Vercel:

1. Set **Root Directory** to `frontend` (Next.js preset, not Services)
2. Set `NEXT_PUBLIC_API_URL` to your backend URL (Railway/Render)
3. Deploy backend separately (see below)

### Backend on Railway / Render

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
