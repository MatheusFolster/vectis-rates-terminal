"""Curva de juros (ETTJ) construída sobre os vértices líquidos de DI1.

Isola a convenção brasileira de capitalização (dias úteis / 252,
composta discreta) e a interpolação (delegada a `MonotonicCubicSpline`)
por trás de uma API só em termos de "dias úteis" e "taxa % a.a.", para
que `metrics.py` e os consumidores externos (API web, scripts) nunca
precisem lidar com a mecânica da spline diretamente.

A taxa de ajuste divulgada pela B3 para um contrato DI1 já É a taxa zero
(spot) da curva para aquele vencimento — DI1 é liquidado por diferença,
sem cupom intermediário — então os vértices líquidos alimentam a spline
diretamente como pares (dias úteis, taxa zero), sem necessidade de
bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

import numpy as np

from ..data.models import DIVertex
from .interpolation import MonotonicCubicSpline

BUSINESS_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class CurvePoint:
    """Um nó de entrada da curva: prazo em dias úteis e taxa zero (% a.a.)."""

    business_days: int
    rate: float


class ETTJCurve:
    """Estrutura a Termo da Taxa de Juros ajustada por spline monotônica.

    Parameters
    ----------
    points:
        Vértices líquidos (dias úteis, taxa % a.a.), já ordenados ou não
        — a curva ordena internamente. Precisa de ao menos 2 pontos.
    trade_date:
        Data de referência (pregão) da curva; usada para converter datas
        de vencimento em dias úteis nas métricas de mais alto nível.
    """

    def __init__(self, points: Sequence[CurvePoint], trade_date: date) -> None:
        if len(points) < 2:
            raise ValueError("ETTJCurve requer ao menos 2 vértices líquidos.")

        ordered = sorted(points, key=lambda p: p.business_days)
        self.trade_date = trade_date
        self.points: tuple[CurvePoint, ...] = tuple(ordered)

        x = np.array([p.business_days for p in ordered], dtype=float)
        y = np.array([p.rate for p in ordered], dtype=float)
        self._spline = MonotonicCubicSpline(x, y, extrapolate="flat")

    @classmethod
    def from_di_vertices(cls, vertices: Sequence[DIVertex]) -> "ETTJCurve":
        if not vertices:
            raise ValueError("Lista de vértices de DI1 vazia.")
        trade_date = vertices[0].trade_date
        points = [
            CurvePoint(business_days=v.business_days_to_maturity, rate=v.settlement_rate)
            for v in vertices
        ]
        return cls(points, trade_date)

    @property
    def min_business_days(self) -> int:
        return int(self.points[0].business_days)

    @property
    def max_business_days(self) -> int:
        return int(self.points[-1].business_days)

    def zero_rate(self, business_days: float) -> float:
        """Taxa zero interpolada (% a.a., base 252) para `business_days`.

        Fora do intervalo [primeiro vértice, último vértice], a curva é
        estendida de forma plana (convenção usual de mercado).
        """
        return float(self._spline(business_days))

    def discount_factor(self, business_days: float) -> float:
        """Fator de desconto DF(t) = (1 + r(t)) ** (-t/252)."""
        r = self.zero_rate(business_days) / 100
        tau = business_days / BUSINESS_DAYS_PER_YEAR
        return (1 + r) ** (-tau)

    def forward_rate(self, business_days_start: float, business_days_end: float) -> float:
        """Taxa a termo discreta (% a.a., base 252) entre dois prazos.

        Taxa implícita entre `business_days_start` e `business_days_end`
        tal que compor a taxa zero até o início com a forward até o fim
        reproduz a taxa zero do prazo final — a mesma mecânica usada pelo
        mercado para precificar um DI a termo (ex.: 1A x 1A).
        """
        if business_days_end <= business_days_start:
            raise ValueError("business_days_end deve ser maior que business_days_start.")

        df_start = self.discount_factor(business_days_start)
        df_end = self.discount_factor(business_days_end)
        tau = (business_days_end - business_days_start) / BUSINESS_DAYS_PER_YEAR
        return ((df_start / df_end) ** (1 / tau) - 1) * 100

    def instantaneous_forward(self, business_days: float) -> float:
        """Taxa forward instantânea em `business_days` (% a.a., base 252).

        Derivada de ln DF(tau) = -tau * ln(1 + r(tau)) em relação a tau,
        primeiro obtida em regime contínuo (f_cont = -d ln DF/d tau) e
        depois convertida para o equivalente anual composto na mesma
        convenção 252 usada pelas taxas zero, para ficar diretamente
        comparável a elas.
        """
        tau = business_days / BUSINESS_DAYS_PER_YEAR
        r = self.zero_rate(business_days) / 100
        dr_dtau = self._spline.derivative(business_days) / 100 * BUSINESS_DAYS_PER_YEAR

        if tau == 0:
            return float(r * 100)

        f_cont = np.log(1 + r) + tau * dr_dtau / (1 + r)
        f_annual = np.exp(f_cont) - 1
        return float(f_annual * 100)
