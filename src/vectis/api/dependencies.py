"""Dependências injetáveis (FastAPI `Depends`) da camada de API."""

from __future__ import annotations

from functools import lru_cache

from ..data import MarketDataRepository


@lru_cache(maxsize=1)
def _repository_singleton() -> MarketDataRepository:
    return MarketDataRepository()


def get_repository() -> MarketDataRepository:
    """Repositório compartilhado entre requisições (mantém as sessões HTTP
    dos clientes de API vivas, em vez de recriar conexões a cada request)."""
    return _repository_singleton()
