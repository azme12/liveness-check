"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from liveness.api.routes import router
from liveness.config import get_settings
from liveness.db import close_db, init_db
from liveness.version import __version__


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    yield
    await close_db()


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
        "description": "Secret API key (never use in mobile apps)",
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Open-source identity verification API — document OCR, passive liveness, "
            "face match, and AML hooks. Built on FastAPI 0.140+ + MongoDB.\n\n"
            "**Auth:** click **Authorize** in Swagger and set `X-Api-Key` "
            "(local default: `sk_test_liveness_dev`).\n\n"
            "**Docs:** Swagger UI `/docs` · ReDoc `/redoc` · OpenAPI `/openapi.json`"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.openapi = lambda: _custom_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
