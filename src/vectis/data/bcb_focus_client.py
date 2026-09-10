"""Cliente da API de Expectativas de Mercado (Relatório Focus/BCB).

Documentação: https://dadosabertos.bcb.gov.br/dataset/expectativas-mercado
Endpoint base (OData): https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/
"""

from __future__ import annotations

from datetime import date

from .http_client import HttpClient
from .models import FocusProjection
from .parsers import parse_iso_date
from .series_codes import FOCUS_INDICATOR_SELIC

_BASE_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativasMercadoAnuais"
)


class BCBFocusClient:
    """Busca a mediana (e estatísticas) das projeções anuais do Focus."""

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self._http = http_client or HttpClient()

    def get_annual_median(
        self,
        indicator: str = FOCUS_INDICATOR_SELIC,
        reference_year: int | None = None,
    ) -> FocusProjection:
        """Retorna a última mediana Focus para `indicator` no ano `reference_year`.

        Por padrão usa o ano corrente (projeção "fim de ano" mais lida pelo
        mercado). `baseCalculo eq 0` = cálculo com todas as respostas dos
        últimos 30 dias, que é o corte padrão usado no terminal.
        """
        year = reference_year or date.today().year

        odata_filter = (
            f"Indicador eq '{indicator}' and "
            f"DataReferencia eq '{year}' and "
            f"baseCalculo eq 0"
        )
        url = (
            f"{_BASE_URL}?$top=1&$orderby=Data desc"
            f"&$filter={odata_filter}&$format=json"
        )

        raw = self._http.get_json(url)
        rows = raw.get("value", [])
        if not rows:
            raise ValueError(
                f"Focus sem dados para indicador={indicator!r} ano={year}"
            )
        row = rows[0]

        return FocusProjection(
            indicator=row["Indicador"],
            reference=row["DataReferencia"],
            reference_date=parse_iso_date(row["Data"]),
            median=float(row["Mediana"]),
            mean=float(row["Media"]),
            std=float(row["DesvioPadrao"]),
            minimum=float(row["Minimo"]),
            maximum=float(row["Maximo"]),
            respondents=int(row["numeroRespondentes"]),
        )
