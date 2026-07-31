from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.db import close_db as close_dashboard_db
from app.db import init_db as init_dashboard_db
from app.routers import auth, dashboard, integration
from app.services.seed import seed_if_empty
from app.services.webhooks import start_webhook_worker, stop_webhook_worker
from liveness.api.routes import router as checks_router
from liveness.config import get_settings as get_liveness_settings
from liveness.db import close_db as close_checks_db
from liveness.db import init_db as init_checks_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    lset = get_liveness_settings()
    lset.storage_dir.mkdir(parents=True, exist_ok=True)
    lset.models_dir.mkdir(parents=True, exist_ok=True)
    await init_checks_db()
    await init_dashboard_db()
    if get_settings().seed_demo:
        await seed_if_empty()
    start_webhook_worker()
    # Warm face model once so uploads don't reload InsightFace per request (OOM on Render).
    try:
        from liveness.ml.face import get_face_analyzer

        get_face_analyzer()
    except Exception:
        pass
    yield
    stop_webhook_worker()
    await close_dashboard_db()
    await close_checks_db()


def _custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-Api-Key",
        "description": "Verification API key (default: sk_test_liveness_dev)",
    }
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Dashboard login JWT from /api/auth/login",
    }
    app.openapi_schema = schema
    return app.openapi_schema


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description=(
            "Trustanova backend — dashboard auth + ComplyCube-style verification checks.\n\n"
            "- **Dashboard:** JWT via `/api/auth/login`\n"
            "- **Checks API:** `X-Api-Key` (default `sk_test_liveness_dev`)"
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Verification checks ( /v1/... , /health )
    app.include_router(checks_router)
    # Dashboard UI API
    app.include_router(auth.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(integration.router, prefix="/api")

    @app.get("/api/health", tags=["system"])
    async def api_health():
        return {"status": "ok", "product": settings.app_name}

    app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
