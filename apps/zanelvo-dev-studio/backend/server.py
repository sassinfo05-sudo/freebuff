"""Zanelvo Dev Studio — standalone FastAPI app entrypoint.

A private, single-user AI software-development environment. It has no customer/tenant concept —
see the app-level CLAUDE.md and README for what this app is and isn't.
"""
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from app import auth as auth_routes  # noqa: E402
from app import config  # noqa: E402
from app.devstudio import routes as devstudio_routes  # noqa: E402
from app.devstudio.db_indexes import ensure_indexes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("devstudio")

app = FastAPI(
    title="Zanelvo Dev Studio",
    description="A private AI software-development environment.",
    version="0.1.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(devstudio_routes.router)


@app.get("/api/health")
async def health():
    from app.db import get_db
    out = {"ok": True, "env": config.APP_ENV}
    try:
        await get_db().command("ping")
        out["db"] = {"ok": True}
    except Exception as e:  # noqa: BLE001
        out["ok"] = False
        out["db"] = {"ok": False, "error": str(e)[:200]}
    return out


@app.on_event("startup")
async def _on_startup():
    if config.is_production() and len(config.JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must be a strong (>=32 char) secret in production")
    try:
        await ensure_indexes()
    except Exception as e:  # noqa: BLE001
        logger.warning("Index creation failed (will retry on next call that needs them): %s", e)


@app.on_event("shutdown")
async def _on_shutdown():
    from app.db import get_client
    get_client().close()
