"""Cliente do portal público de dados da B3 (arquivos.b3.com.br/bdi).

A B3 não oferece uma API REST pública e documentada para os ajustes
diários de derivativos. O endpoint usado aqui foi identificado no bundle
JavaScript do próprio portal BDI (https://arquivos.b3.com.br/bdi/), que
usa `POST /bdi/table/export/csv` para exportar em CSV a mesma grade
mostrada na tela.

Tabela usada: "ConsolidatedTradesDerivatives" (Negócios consolidados do
pregão) — contém, por instrumento negociado no dia, preço/taxa de ajuste,
ajuste anterior, quantidade de contratos e volume financeiro.

Por depender de um endpoint não documentado, isolamos aqui toda a lógica
de requisição e parsing do CSV bruto, para que uma eventual mudança da B3
exija alterar só este arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import requests

_EXPORT_URL = "https://arquivos.b3.com.br/bdi/table/export/csv"
_TABLE_NAME = "ConsolidatedTradesDerivatives"
_HEADER_MARKER = "Instrumento financeiro"
_USER_AGENT = "Mozilla/5.0 (compatible; VectisRatesTerminal/1.0)"

# Índices das colunas relevantes no CSV exportado pelo portal BDI.
_COL_INSTRUMENT = 0
_COL_SETTLEMENT_PU = 9  # "Ajuste" (PU)
_COL_SETTLEMENT_RATE = 10  # "Ajuste de referência" (taxa % equivalente ao PU)
_COL_PREVIOUS_SETTLEMENT_PU = 11  # "Ajuste do dia anterior"
_COL_TRADES_COUNT = 17  # "Quantidade de negócios"
_COL_CONTRACTS_COUNT = 18  # "Quantidade de contratos"
_COL_FINANCIAL_VOLUME = 19  # "Volume financeiro"
_MIN_COLUMNS = 20


class B3RequestError(RuntimeError):
    """Erro ao consultar ou interpretar o portal de dados públicos da B3."""


@dataclass(frozen=True, slots=True)
class DerivativeSettlementRow:
    """Uma linha crua do boletim de negócios consolidados de derivativos."""

    instrument: str
    settlement_pu: float
    settlement_rate: float
    previous_settlement_pu: float
    trades_count: int
    contracts_count: int
    financial_volume: float


class B3DIClient:
    """Busca o boletim diário de derivativos de bolsa (inclui DI1 futuro)."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _USER_AGENT})

    def get_settlement_rows(self, reference_date: date) -> list[DerivativeSettlementRow]:
        """Baixa e interpreta o boletim de derivativos de `reference_date`."""
        date_str = reference_date.isoformat()
        body = {
            "Name": _TABLE_NAME,
            "Date": date_str,
            "FinalDate": date_str,
            "ClientId": "",
            "Filters": {},
        }
        try:
            response = self._session.post(_EXPORT_URL, json=body, timeout=self._timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise B3RequestError(
                f"Falha ao consultar boletim de derivativos da B3 ({date_str}): {exc}"
            ) from exc

        return self._parse_csv(response.content, reference_date)

    @staticmethod
    def _parse_csv(raw: bytes, reference_date: date) -> list[DerivativeSettlementRow]:
        text = raw.decode("utf-8-sig")
        lines = text.splitlines()

        header_idx = next(
            (i for i, line in enumerate(lines) if line.startswith(_HEADER_MARKER)),
            None,
        )
        if header_idx is None:
            raise B3RequestError(
                f"Boletim da B3 sem o cabeçalho esperado para {reference_date.isoformat()} "
                "(pode ser dia sem pregão ou o layout do portal mudou)."
            )

        rows: list[DerivativeSettlementRow] = []
        for line in lines[header_idx + 1 :]:
            if not line.strip():
                continue
            fields = line.split(";")
            if len(fields) < _MIN_COLUMNS:
                continue
            rows.append(
                DerivativeSettlementRow(
                    instrument=fields[_COL_INSTRUMENT],
                    settlement_pu=_to_float(fields[_COL_SETTLEMENT_PU]),
                    settlement_rate=_to_float(fields[_COL_SETTLEMENT_RATE]),
                    previous_settlement_pu=_to_float(fields[_COL_PREVIOUS_SETTLEMENT_PU]),
                    trades_count=int(_to_float(fields[_COL_TRADES_COUNT])),
                    contracts_count=int(_to_float(fields[_COL_CONTRACTS_COUNT])),
                    financial_volume=_to_float(fields[_COL_FINANCIAL_VOLUME]),
                )
            )
        return rows


def _to_float(value: str) -> float:
    """Converte número no formato B3 (milhar '.', decimal ',') para float."""
    value = value.strip()
    if value in ("", "-"):
        return 0.0
    return float(value.replace(".", "").replace(",", "."))
