"""
server.py — FastAPI application factory + uvicorn launcher.
"""
from __future__ import annotations

import webbrowser
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dsviewer import auth as _auth
from dsviewer import api as _api
from dsviewer.config import AppConfig

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application."""
    # Wire config into modules that need it
    _auth.set_config(config)
    _api.set_config(config)

    app = FastAPI(title="Directory Structure Viewer", version="1.0.0")

    # -----------------------------------------------------------------------
    # CORS — allow all origins (local developer tool)
    # -----------------------------------------------------------------------

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Global exception handler — always return JSON
    # -----------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def generic_error_handler(request, exc):
        return JSONResponse(
            status_code=getattr(exc, "status_code", 500),
            content={"error": str(exc)},
        )

    # -----------------------------------------------------------------------
    # API router
    # -----------------------------------------------------------------------

    app.include_router(_api.router)

    # -----------------------------------------------------------------------
    # Frontend SPA — serve index.html at / and fall back for any unknown route
    # -----------------------------------------------------------------------

    @app.get("/")
    async def serve_index():
        return FileResponse(_STATIC_DIR / "index.html")

    # Serve any other static assets that may be present
    if _STATIC_DIR.is_dir():
        # Mount static files (but not at root — that would conflict with /api)
        pass

    # Catch-all: serve index.html for any path not matched above (SPA routing)
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        static_file = _STATIC_DIR / full_path
        if static_file.is_file():
            return FileResponse(static_file)
        return FileResponse(_STATIC_DIR / "index.html")

    return app


def run(config: AppConfig) -> None:
    """Bootstrap data directory, then launch uvicorn."""
    import uvicorn

    config.ensure_data_dir()
    app = create_app(config)

    print(f"  Directory Structure Viewer")
    print(f"  Listening on http://{config.host}:{config.port}")
    if config.no_auth:
        print("  ⚠  Authentication DISABLED (--no-auth mode)")
    print(f"  Data directory: {config.data_dir}")
    print("  Press Ctrl+C to stop\n")

    if config.open_browser:
        import threading
        def _open():
            import time
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{config.port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="warning",
    )
