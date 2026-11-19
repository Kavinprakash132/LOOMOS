"""FastAPI application entrypoint for LOOMOS."""

from __future__ import annotations

from pathlib import Path
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import BACKEND_ROOT, get_settings
from app.core.database import Base, engine
from app.core.i18n import get_translations
from app.routers import analytics, auth, beams, dashboard, data_ops, finance, inspections, masters, payroll, settings as settings_router, setup, shifts


def create_app() -> FastAPI:
    """Build and configure the LOOMOS FastAPI application."""
    cfg = get_settings()
    app = FastAPI(
        title="LOOMOS API",
        version="0.2.0",
        description="Mobile-first Powerloom Job-Work Production, Analytics & Defect Inspection System",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(setup.router)
    app.include_router(auth.router)
    app.include_router(settings_router.router)
    app.include_router(masters.router)
    app.include_router(beams.router)
    app.include_router(shifts.router)
    app.include_router(payroll.router)
    app.include_router(finance.router)
    app.include_router(data_ops.router)
    app.include_router(dashboard.router)
    app.include_router(inspections.router)
    app.include_router(analytics.router)

    @app.get("/api/v1/health", tags=["system"])
    def health_check() -> dict[str, str]:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "app": cfg.app_name}

    @app.get("/api/v1/i18n/{lang}", tags=["i18n"])
    def fetch_translations(lang: str) -> dict[str, str]:
        return get_translations(lang)

    # Single-container production mode: serve built React SPA if frontend/dist exists
    dist_env = os.environ.get("LOOMOS_FRONTEND_DIST")
    frontend_dist = Path(dist_env) if dist_env else (BACKEND_ROOT.parent / "frontend" / "dist")
    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")

        index_html = frontend_dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API endpoint not found")
            candidate = (frontend_dist / full_path).resolve()
            if (
                full_path
                and candidate.is_file()
                and frontend_dist.resolve() in candidate.parents
            ):
                return FileResponse(str(candidate))
            return FileResponse(str(index_html))

    return app


app = create_app()
