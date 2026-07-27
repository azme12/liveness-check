# Trustanova

**Trustanova** is the ComplyCube-style product UI for this repo:

| Folder | Stack | Port | Role |
|--------|-------|------|------|
| `frontend/` | Next.js 15 | **3000** | Dashboard (login, home, clients, sessions, checks, workflows, integration) |
| `backend/` | FastAPI | **8100** | Dashboard + verification API |

## Quick start (local)

```bash
# 1) Mongo + backend
docker compose up -d mongo

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
LIVENCUBE_MONGODB_URL=mongodb://127.0.0.1:27018 \
LIVENESS_MONGODB_URL=mongodb://127.0.0.1:27018 \
uvicorn app.main:app --reload --port 8100

# 2) Frontend
cd ../frontend
cp .env.local.example .env.local   # if needed
npm install
npm run dev
```

Open **http://127.0.0.1:3000**

### Demo login

- Email: `admin@trustanova.dev`
- Password: `admin123`

Or use **Sign up** to create a new org.

## URLs

- Front: http://127.0.0.1:3000
- API docs: http://127.0.0.1:8100/docs
- Mongo Express: http://127.0.0.1:8081
