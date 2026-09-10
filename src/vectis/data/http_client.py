"""Cliente HTTP genérico usado por todos os provedores de dados.

Isolar a camada de transporte (sessão, timeout, retries, tratamento de
erro) aqui permite que os clientes de API (SGS, Focus, B3...) fiquem
enxutos e só se preocupem com a URL/parsing de cada provedor.
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT_SECONDS = 15


class BCBRequestError(RuntimeError):
    """Erro ao consultar uma API do Banco Central (SGS, Focus, etc.)."""


class HttpClient:
    """Wrapper fino sobre requests.Session com retry e timeout padrão."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise BCBRequestError(f"Falha ao consultar {url}: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise BCBRequestError(
                f"Resposta inválida (não é JSON) de {url}: {response.text[:200]}"
            ) from exc
