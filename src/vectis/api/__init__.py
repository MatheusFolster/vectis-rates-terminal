"""Camada de API (FastAPI) do Vectis Rates Terminal.

Expõe `vectis.data` e `vectis.quant` como endpoints HTTP consumidos pelo
frontend (`vectis.web`): indicadores, curva ETTJ interpolada e busca.
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
