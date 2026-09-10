"""Monta a aplicação FastAPI: routers da API + página do terminal."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routers import curve, indicators, search

_WEB_DIR = Path(__file__).resolve().parents[1] / "web"
_templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="Vectis Rates Terminal", version="0.1.0")

    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")

    app.include_router(indicators.router)
    app.include_router(curve.router)
    app.include_router(search.router)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(request, "index.html", {})

    return app


app = create_app()
