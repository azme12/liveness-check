# Trustanova backend

Unified FastAPI service:

- Dashboard: `/api/auth`, `/api/clients`, `/api/workflows`, `/api/integration/*`
- Verification: `/v1/*`, `/health`

```bash
pip install -r requirements.txt && pip install -e .
LIVENCUBE_MONGODB_URL=mongodb://127.0.0.1:27018 \
LIVENESS_MONGODB_URL=mongodb://127.0.0.1:27018 \
uvicorn app.main:app --reload --port 8100
```
