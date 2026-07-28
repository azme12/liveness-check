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
- **Create account:** open `/signup` (stored in MongoDB)  
- Optional local demo: set `LIVENCUBE_SEED_DEMO=true` then restart backend (`admin@trustanova.dev` / `admin123`)

## Docker (all)

```bash
docker compose up --build -d
```

## Deploy (production)

| Component | Host | Notes |
|-----------|------|--------|
| **Frontend** | [Vercel](https://vercel.com) | Root directory: `frontend` |
| **Backend** | [Render](https://render.com) | Docker service from `backend/` |
| **Database** | [MongoDB Atlas](https://www.mongodb.com/atlas) | Connection string for backend |

### 1. Backend on Render

1. Create a [MongoDB Atlas](https://www.mongodb.com/atlas) cluster and get a connection string.
2. In Render → **New → Blueprint** (or Web Service) → connect `azme12/liveness-check`.
3. Use the included [`render.yaml`](render.yaml), or create a **Web Service** manually:
   - **Root Directory:** `backend`
   - **Runtime:** Docker (`Dockerfile`)
   - **Health check:** `/health`
4. Set environment variables:

```bash
LIVENCUBE_MONGODB_URL=mongodb+srv://USER:PASS@cluster.mongodb.net/liveness
LIVENCUBE_MONGODB_DB=liveness
LIVENCUBE_JWT_SECRET=<strong-random-secret>
LIVENCUBE_CORS_ORIGINS=https://your-app.vercel.app
LIVENESS_MONGODB_URL=mongodb+srv://USER:PASS@cluster.mongodb.net/liveness
LIVENESS_MONGODB_DB=liveness
```

5. Deploy. Note your public URL, e.g. `https://liveness-api.onrender.com`.

> After the frontend URL is known, update `LIVENCUBE_CORS_ORIGINS` to match (comma-separated if you need localhost too).

### 2. Frontend on Vercel

1. Import the repo on Vercel → **Next.js** preset (not Services).
2. Set **Root Directory** to `frontend`.
3. Add environment variable:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | `https://liveness-api.onrender.com` (your Render URL, no trailing slash) |

4. Deploy. Login: create an account via **Sign up** (data is stored in MongoDB Atlas).

## Layout

| Path | Purpose |
|------|---------|
| `frontend/` | Login, Home, Clients, Sessions, Checks, Workflows, Integration |
| `backend/app/` | Dashboard API (auth, workflows, webhooks, …) |
| `backend/src/liveness/` | Verification engine (`/v1/clients`, `/v1/checks`, …) |
| `backend/tests/` | Pytest suite |
