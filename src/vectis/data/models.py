"""Estruturas de dados da camada de ingestão (vectis.data).

Isolamos os modelos aqui para que clientes de API, repositório e camadas
futuras (motor quant, API web) compartilhem os mesmos tipos sem depender
de detalhes de parsing HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    """Um ponto (data, valor) de uma série temporal do SGS."""

    date: date
    value: float


@dataclass(slots=True)
class TimeSeries:
    """Série temporal tratada, pronta tanto para exibição pontual (cards)
    quanto para uso em séries históricas (ex.: interpolação futura da ETTJ).
    """

    code: str
    name: str
    source: str
    points: list[SeriesPoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.points.sort(key=lambda p: p.date)

    def latest(self) -> SeriesPoint | None:
        return self.points[-1] if self.points else None

    def to_dataframe(self) -> pd.DataFrame:
        """Retorna DataFrame indexado por data, coluna 'value'.

        Formato genérico reutilizável tanto pelos cards de indicadores
        quanto pelo bootstrap/spline da curva ETTJ mais adiante.
        """
        if not self.points:
            return pd.DataFrame(columns=["value"]).astype({"value": "float64"})
        df = pd.DataFrame(
            {"value": [p.value for p in self.points]},
            index=pd.DatetimeIndex([p.date for p in self.points], name="date"),
        )
        return df


@dataclass(frozen=True, slots=True)
class FocusProjection:
    """Mediana (e estatísticas) do Relatório Focus para um indicador/ano-base."""

    indicator: str
    reference: str
    reference_date: date
    median: float
    mean: float
    std: float
    minimum: float
    maximum: float
    respondents: int
    source: str = "BCB/Focus"


@dataclass(frozen=True, slots=True)
class DIVertex:
    """Um vértice líquido da curva de DI futuro (B3), pronto para o bootstrap
    e a spline da ETTJ: já traz prazo em dias úteis e taxa de ajuste.
    """

    code: str
    maturity: date
    business_days_to_maturity: int
    settlement_rate: float
    settlement_pu: float
    contracts_traded: int
    financial_volume: float
    trade_date: date


@dataclass(frozen=True, slots=True)
class MarketIndicators:
    """Snapshot agregado, pronto para abastecer os cards do terminal."""

    selic_meta: SeriesPoint
    selic_efetiva_anualizada: SeriesPoint
    ipca_mensal: SeriesPoint
    focus_selic: FocusProjection
    generated_at: datetime
