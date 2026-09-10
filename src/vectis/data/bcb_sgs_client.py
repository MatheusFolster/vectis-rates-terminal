"""Cliente do Sistema Gerenciador de Séries Temporais (SGS/BCB).

Documentação: https://dadosabertos.bcb.gov.br/dataset/xxxx (API SGS)
Endpoint base: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
"""

from __future__ import annotations

from datetime import date

from .http_client import HttpClient
from .models import SeriesPoint, TimeSeries
from .parsers import parse_br_date, parse_number
from .series_codes import SGSSeriesDef

_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"


class BCBSGSClient:
    """Busca séries temporais oficiais do SGS (Selic, IPCA, etc.)."""

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self._http = http_client or HttpClient()

    def get_series(
        self,
        series: SGSSeriesDef,
        last_n: int | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> TimeSeries:
        """Baixa uma série do SGS e retorna já tratada como TimeSeries.

        Use `last_n` para os últimos N valores publicados, ou `start`/`end`
        para uma janela específica. Sem nenhum filtro, o SGS retorna a
        série completa (pode ser grande).
        """
        url = _BASE_URL.format(code=series.code)
        params: dict[str, str] = {"formato": "json"}

        if last_n is not None:
            url += f"/ultimos/{last_n}"
        else:
            if start is not None:
                params["dataInicial"] = start.strftime("%d/%m/%Y")
            if end is not None:
                params["dataFinal"] = end.strftime("%d/%m/%Y")

        raw = self._http.get_json(url, params=params)

        points = [
            SeriesPoint(date=parse_br_date(row["data"]), value=parse_number(row["valor"]))
            for row in raw
        ]

        return TimeSeries(
            code=str(series.code),
            name=series.name,
            source=series.source,
            points=points,
        )
