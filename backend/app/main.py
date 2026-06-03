"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_auth, routes_export, routes_patients, routes_sessions, ws
from app.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description="Infant thermal monitoring backend for the GW192A camera platform.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_auth.router)
    app.include_router(routes_patients.router)
    app.include_router(routes_sessions.router)
    app.include_router(routes_export.router)
    app.include_router(ws.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}

    @app.get("/api/config", tags=["meta"])
    def public_config() -> dict:
        """Non-secret config the frontend needs (thresholds, palettes, geometry)."""
        return {
            "geometry": {"width": settings.sensor_width, "height": settings.sensor_height},
            "palettes": ["iron", "rainbow", "white_hot", "black_hot", "medical", "grayscale"],
            "thresholds": {
                "body": {"normal": [36.5, 37.5], "critical": [36.0, 38.0]},
                "ambient": {"normal": [20.0, 24.0]},
            },
        }

    return app


app = create_app()
